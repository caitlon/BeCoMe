"""Integration tests for the per-account counter on current-password checks.

The test app runs with the rate limiter off, so a 400 or a 204 proves little by itself. Each
test reads the counter in a fakeredis store, or the state the operation leaves behind (the
stored hash, the account row), to show the mechanism ran.
"""

import logging
from contextlib import contextmanager
from uuid import UUID

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient
from sqlmodel import select

from api.auth.login_throttle import (
    LOGIN_KEY_PREFIX,
    RECONFIRM_KEY_PREFIX,
    RedisLoginThrottle,
    get_current_password_throttle,
    get_login_throttle,
)
from api.auth.revocation_store import InMemoryRevocationStore, get_revocation_store
from api.db.models import User
from api.dependencies import get_email_service
from tests.integration.api.auth.conftest import FakeEmailSender
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    app_session,
    auth_header,
    create_project,
    delete_account,
    register_and_login,
)

WRONG_PASSWORD = "NotThePassword1!"  # pragma: allowlist secret
NEW_PASSWORD = "NewSecurePass456!"  # pragma: allowlist secret
THIRD_PASSWORD = "ThirdSecurePass789!"  # pragma: allowlist secret
CHANGE_URL = "/api/v1/users/me/password"
LOCKED_DETAIL = "Too many failed password attempts. Please try again later."
THRESHOLD = 10
LOCKED_EMAIL = "locked@example.com"
COUNTER_KEYS = f"{RECONFIRM_KEY_PREFIX}:fail:*"
LOGIN_KEYS = f"{LOGIN_KEY_PREFIX}:fail:*"


class _KeepSessionsStore(InMemoryRevocationStore):
    """A revocation store that never records the cutoff a password change sets.

    A change revokes earlier tokens, and one minted in the same second as the cutoff is
    refused too, so a test that keeps using the account after a change swaps this in.
    """

    def set_user_valid_after(self, user_id, valid_after) -> None:
        """Ignore the cutoff."""


@pytest.fixture
def store(client: TestClient) -> fakeredis.FakeStrictRedis:
    """A fake Redis behind the current-password throttle."""
    fake = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())
    throttle = RedisLoginThrottle(fake, key_prefix=RECONFIRM_KEY_PREFIX)
    client.app.dependency_overrides[get_current_password_throttle] = lambda: throttle
    return fake


@pytest.fixture
def login_throttle(client: TestClient, store) -> RedisLoginThrottle:
    """The login throttle, on the same fake store as the current-password one."""
    chosen = RedisLoginThrottle(store, key_prefix=LOGIN_KEY_PREFIX)
    client.app.dependency_overrides[get_login_throttle] = lambda: chosen
    return chosen


@contextmanager
def _captured(name: str):
    """Yield the records ``name`` emits inside the block, whatever the logging setup did."""
    target = logging.getLogger(name)
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append  # type: ignore[method-assign]
    previous = target.level
    target.addHandler(handler)
    target.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        target.removeHandler(handler)
        target.setLevel(previous)


def _change(client: TestClient, token: str, current: str, new: str = NEW_PASSWORD):
    """Send a password change."""
    return client.put(
        CHANGE_URL,
        json={"current_password": current, "new_password": new},
        headers=auth_header(token),
    )


def _user_id(client: TestClient, token: str) -> UUID:
    return UUID(client.get("/api/v1/auth/me", headers=auth_header(token)).json()["id"])


def _stored_hash(client: TestClient, user_id: UUID) -> str | None:
    """Return the account's stored password hash, or None when the account is gone."""
    with app_session(client) as session:
        user = session.exec(select(User).where(User.id == user_id)).first()
        return user.hashed_password if user else None


def _counter(store) -> int | None:
    """Return the single current-password counter in the store, or None when absent."""
    keys = store.keys(COUNTER_KEYS)
    assert len(keys) <= 1
    return int(store.get(keys[0])) if keys else None


def _fail_on_both_routes(client: TestClient, token: str, each: int) -> None:
    """Send ``each`` wrong-password changes and as many wrong-password deletions."""
    for _ in range(each):
        assert _change(client, token, WRONG_PASSWORD).status_code == 400
        assert delete_account(client, token, password=WRONG_PASSWORD).status_code == 400


@pytest.fixture
def locked_token(client: TestClient, store) -> str:
    """The token of an account locked by ten wrong current passwords."""
    token = register_and_login(client, LOCKED_EMAIL)
    for _ in range(THRESHOLD):
        _change(client, token, WRONG_PASSWORD)
    return token


class TestFailuresAddUpAcrossRoutes:
    """One counter per account serves the change and the deletion alike."""

    def test_failures_on_both_routes_lock_both(self, client, store):
        """
        GIVEN five wrong passwords on the change and five on the deletion
        WHEN the eleventh attempt comes with the correct password, on each route
        THEN both answer 429, the hash is unchanged and the account still exists
        """
        token = register_and_login(client, "adds-up@example.com")
        user_id = _user_id(client, token)
        hash_before = _stored_hash(client, user_id)
        _fail_on_both_routes(client, token, each=THRESHOLD // 2)
        assert _counter(store) == THRESHOLD

        change = _change(client, token, DEFAULT_TEST_PASSWORD)
        deletion = delete_account(client, token)

        assert (change.status_code, deletion.status_code) == (429, 429)
        assert _stored_hash(client, user_id) == hash_before

    def test_a_correct_password_resets_the_count(self, client, store):
        """
        GIVEN nine wrong passwords, then the correct one on a password change
        WHEN nine more wrong ones follow
        THEN the account is not locked and a correct change still goes through

        The change revokes the session, so the revocation store is swapped for one that
        keeps the token alive and the same token carries the whole scenario.
        """
        client.app.dependency_overrides[get_revocation_store] = _KeepSessionsStore
        token = register_and_login(client, "resets@example.com")
        for _ in range(THRESHOLD - 1):
            assert _change(client, token, WRONG_PASSWORD).status_code == 400
        assert _counter(store) == THRESHOLD - 1

        assert _change(client, token, DEFAULT_TEST_PASSWORD).status_code == 204
        assert _counter(store) is None
        for _ in range(THRESHOLD - 1):
            assert _change(client, token, WRONG_PASSWORD).status_code == 400

        assert _counter(store) == THRESHOLD - 1
        assert _change(client, token, NEW_PASSWORD, THIRD_PASSWORD).status_code == 204

    def test_one_accounts_lock_leaves_another_alone(self, client, locked_token):
        """
        GIVEN one account locked out
        WHEN a different account changes its password
        THEN that change succeeds, and a wrong password there is a plain 400
        """
        assert _change(client, locked_token, DEFAULT_TEST_PASSWORD).status_code == 429
        other = register_and_login(client, "bystander@example.com")

        assert _change(client, other, WRONG_PASSWORD).status_code == 400
        assert _change(client, other, DEFAULT_TEST_PASSWORD).status_code == 204


class TestLoginCounterIsSeparate:
    """A stolen session must not be able to lock the owner out of signing in."""

    def test_the_two_counters_do_not_touch_each_other(self, client, store, login_throttle):
        """
        GIVEN three wrong current passwords on each route
        THEN only the current-password counter moved, and login is not locked
        WHEN the login counter is then locked
        THEN the right password still changes the password and deletes the account, and a
            wrong one reads as 400, not 429
        """
        email = "counters@example.com"
        client.app.dependency_overrides[get_revocation_store] = _KeepSessionsStore
        token = register_and_login(client, email)
        user_id = _user_id(client, token)
        _fail_on_both_routes(client, token, each=3)
        assert _counter(store) == 6
        assert store.keys(LOGIN_KEYS) == []
        assert login_throttle.is_locked(email) is False

        for _ in range(THRESHOLD):
            login_throttle.record_failure(email)
        assert login_throttle.is_locked(email) is True

        assert _change(client, token, WRONG_PASSWORD).status_code == 400
        assert _change(client, token, DEFAULT_TEST_PASSWORD).status_code == 204
        assert delete_account(client, token, password=NEW_PASSWORD).status_code == 204
        assert _stored_hash(client, user_id) is None
        assert _counter(store) is None


class TestPasswordReset:
    """A reset clears the lock, because it signs every session out."""

    def _reset(self, client: TestClient, token: str | None = None) -> int:
        """Reset the locked account's password with ``token``, or the mailed one by default."""
        sender = FakeEmailSender()
        client.app.dependency_overrides[get_email_service] = lambda: sender
        client.post("/api/v1/auth/forgot-password", json={"email": LOCKED_EMAIL})
        mailed = sender.calls[-1]["reset_url"].split("token=")[1]
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token or mailed, "new_password": THIRD_PASSWORD},
        )
        return response.status_code

    def test_a_completed_reset_clears_the_lock(self, client, store, locked_token):
        """
        GIVEN an account locked by ten wrong current passwords
        WHEN its owner completes a password reset
        THEN the counter is gone, and it was still locked just before the reset
        """
        user_id = _user_id(client, locked_token)
        assert _counter(store) == THRESHOLD
        throttle = RedisLoginThrottle(store, key_prefix=RECONFIRM_KEY_PREFIX)
        assert throttle.is_locked(str(user_id)) is True

        assert self._reset(client) == 204

        assert store.keys(COUNTER_KEYS) == []
        assert throttle.is_locked(str(user_id)) is False

    def test_an_invalid_token_leaves_the_lock_in_place(self, client, store, locked_token):
        """
        GIVEN an account locked by ten wrong current passwords
        WHEN a reset arrives with a token that does not exist
        THEN it is refused with 400 and the counter is untouched
        """
        assert self._reset(client, token="not-a-real-token") == 400

        assert _counter(store) == THRESHOLD


class TestStoreUnavailable:
    """The counter fails open like the login one, and says so."""

    def test_an_unreachable_store_does_not_gate_the_routes(self, client):
        """
        GIVEN a throttle whose store raises on every call
        WHEN a wrong password and then the correct one arrive
        THEN the wrong one is a 400 with its code, the right one changes the password,
            and throttle_store_unavailable is logged at ERROR under the new key prefix
        """
        down = fakeredis.FakeServer()
        down.connected = False
        broken = RedisLoginThrottle(
            fakeredis.FakeStrictRedis(server=down), key_prefix=RECONFIRM_KEY_PREFIX
        )
        client.app.dependency_overrides[get_current_password_throttle] = lambda: broken
        token = register_and_login(client, "store-down@example.com")
        user_id = _user_id(client, token)
        hash_before = _stored_hash(client, user_id)

        with _captured("api.security") as records:
            wrong = _change(client, token, WRONG_PASSWORD)
            right = _change(client, token, DEFAULT_TEST_PASSWORD)

        assert wrong.status_code == 400
        assert wrong.json()["code"] == "current_password_incorrect"
        assert right.status_code == 204
        assert _stored_hash(client, user_id) != hash_before
        outages = [r for r in records if getattr(r, "event", None) == "throttle_store_unavailable"]
        assert {r.op for r in outages} == {"reserve", "confirm_failure", "reset"}
        assert {r.key_prefix for r in outages} == {RECONFIRM_KEY_PREFIX}
        assert {r.levelno for r in outages} == {logging.ERROR}
        assert all(isinstance(r.exc_info[1], redis.RedisError) for r in outages)


class TestRefusal:
    """What the locked caller sees, and what the log keeps."""

    def test_the_answer_is_a_429_with_its_own_wording_before_any_other_check(
        self, client, locked_token
    ):
        """
        GIVEN a locked account that owns a project
        WHEN it asks to delete itself with the correct password and no disposition
        THEN the answer is 429 with the password wording, not the 409 about the project,
            so the lock came before any other check
        """
        create_project(client, locked_token)

        response = delete_account(client, locked_token)

        assert response.status_code == 429
        assert response.json() == {"detail": LOCKED_DETAIL}

    def test_a_lock_holds_from_another_address_and_is_logged_without_the_account(
        self, client, locked_token
    ):
        """
        GIVEN an account locked by attempts from one address
        WHEN the same session asks from a different one with the correct password
        THEN it is refused with 429, and current_password_locked is logged with that address
            and the path, with nothing in the record naming the email or a digest of it
        """
        remote = TestClient(client.app, client=("198.51.100.7", 50000))

        with _captured("api.security") as records:
            response = _change(remote, locked_token, DEFAULT_TEST_PASSWORD)

        locked = [r for r in records if getattr(r, "event", None) == "current_password_locked"]
        assert response.status_code == 429
        assert len(locked) == 1
        assert (locked[0].ip, locked[0].path) == ("198.51.100.7", CHANGE_URL)
        assert not {"email", "email_hash", "digest"} & set(vars(locked[0]))
        assert LOCKED_EMAIL not in str(vars(locked[0]))
