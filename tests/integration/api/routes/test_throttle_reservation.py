"""Integration tests for the attempt reservation taken before a password is checked.

The test app runs with the rate limiter off, so a status code alone proves little. Every test
reads the counters in a fakeredis store as well, to show the mechanism ran. The parallel test
holds the password checks open on a barrier so the requests really overlap, which is the only
way to tell a reservation from a read taken before the check.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress

import fakeredis
import pytest
from fastapi.testclient import TestClient

from api.auth.login_throttle import (
    ACTIVATION_KEY_PREFIX,
    LOGIN_KEY_PREFIX,
    MAX_FAILURES,
    RECONFIRM_KEY_PREFIX,
    RedisLoginThrottle,
    get_activation_throttle,
    get_current_password_throttle,
    get_login_throttle,
)
from api.exceptions import InvalidCredentialsError
from api.services.user_service import UserService
from tests.integration.api.conftest import (
    DEFAULT_TEST_PASSWORD,
    auth_header,
    register,
    register_and_login,
    register_verified,
)

LOGIN_URL = "/api/v1/auth/login"
VERIFY_URL = "/api/v1/auth/verify-email"
CHANGE_URL = "/api/v1/users/me/password"
WRONG_PASSWORD = "NotThePassword1!"  # pragma: allowlist secret
NEW_PASSWORD = "NewSecurePass456!"  # pragma: allowlist secret
BURST = 2 * MAX_FAILURES
BARRIER_TIMEOUT = 15


@pytest.fixture
def store(client: TestClient) -> fakeredis.FakeStrictRedis:
    """A fake Redis behind all three throttles, each under its own prefix."""
    fake = fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())
    overrides = client.app.dependency_overrides
    for factory, prefix in (
        (get_login_throttle, LOGIN_KEY_PREFIX),
        (get_activation_throttle, ACTIVATION_KEY_PREFIX),
        (get_current_password_throttle, RECONFIRM_KEY_PREFIX),
    ):
        overrides[factory] = _provide(RedisLoginThrottle(fake, key_prefix=prefix))
    return fake


def _provide(throttle: RedisLoginThrottle):
    """Return a dependency override that hands out ``throttle``."""
    return lambda: throttle


def _counter(store: fakeredis.FakeStrictRedis, prefix: str) -> int | None:
    """Return the single counter under ``prefix``, or None when the store holds none."""
    keys = store.keys(f"{prefix}:fail:*")
    assert len(keys) <= 1
    return int(store.get(keys[0])) if keys else None


def _login(client: TestClient, email: str, password: str):
    return client.post(LOGIN_URL, data={"username": email, "password": password})


def _activate(client: TestClient, token: str, password: str):
    return client.post(VERIFY_URL, json={"token": token, "password": password})


def _change(client: TestClient, token: str, current: str):
    return client.put(
        CHANGE_URL,
        json={"current_password": current, "new_password": NEW_PASSWORD},
        headers=auth_header(token),
    )


@contextmanager
def _patched(target: str, replacement):
    """Swap ``UserService.<target>`` for ``replacement`` while the block runs."""
    original = getattr(UserService, target)
    setattr(UserService, target, replacement)
    try:
        yield
    finally:
        setattr(UserService, target, original)


def _verification_raises(target: str, error: Exception):
    """Make ``UserService.<target>`` raise ``error``, as a crash inside the check would."""

    def boom(*_args, **_kwargs):
        raise error

    return _patched(target, boom)


class TestParallelLogin:
    """Requests that overlap cannot buy more password checks than the budget."""

    def test_a_burst_of_wrong_passwords_gets_exactly_the_budget_of_checks(self, client, store):
        """
        GIVEN one account and twice the budget of wrong-password logins sent together,
            each password check held open until a budget's worth of them overlap
        WHEN they all land
        THEN exactly the budget of checks ran, the counter reads the budget, and the answers
            are that many 401s with the rest 429

        The rate limiter is off here, so the counter and the number of checks are what show
        the reservation worked.
        """
        register_verified(client, "burst@example.com")
        checks = 0
        checks_lock = threading.Lock()
        overlap = threading.Barrier(MAX_FAILURES, timeout=BARRIER_TIMEOUT)

        def slow_wrong_check(_self, email: str, _password: str):
            nonlocal checks
            with checks_lock:
                checks += 1
            with suppress(threading.BrokenBarrierError):
                overlap.wait()
            raise InvalidCredentialsError("Invalid email or password", email=email)

        go = threading.Barrier(BURST, timeout=BARRIER_TIMEOUT)

        def post() -> int:
            go.wait()
            return _login(TestClient(client.app), "burst@example.com", WRONG_PASSWORD).status_code

        with (
            _patched("authenticate", slow_wrong_check),
            ThreadPoolExecutor(max_workers=BURST) as pool,
        ):
            answers = [future.result() for future in [pool.submit(post) for _ in range(BURST)]]

        assert checks == MAX_FAILURES
        assert _counter(store, LOGIN_KEY_PREFIX) == MAX_FAILURES
        assert sorted(answers) == [401] * MAX_FAILURES + [429] * (BURST - MAX_FAILURES)


class TestSlotsGivenBack:
    """An attempt that was neither a failed guess nor a success spends nothing."""

    def test_a_correct_password_on_an_unverified_account_never_locks_it(self, client, store):
        """
        GIVEN an account whose address is not verified yet
        WHEN its correct password is sent more times than the budget
        THEN every answer is the 403 and the counter never moved
        """
        register(client, "unverified@example.com")

        answers = [
            _login(client, "unverified@example.com", DEFAULT_TEST_PASSWORD).status_code
            for _ in range(MAX_FAILURES + 2)
        ]

        assert answers == [403] * (MAX_FAILURES + 2)
        assert _counter(store, LOGIN_KEY_PREFIX) is None

    def test_a_crash_during_login_leaves_the_counter_alone(self, client, store):
        """
        GIVEN a login whose password check crashes
        WHEN the request is sent
        THEN the answer is a 500 and the counter is untouched
        """
        register_verified(client, "crash@example.com")
        failing = TestClient(client.app, raise_server_exceptions=False)

        with _verification_raises("authenticate", RuntimeError("boom")):
            response = _login(failing, "crash@example.com", DEFAULT_TEST_PASSWORD)

        assert response.status_code == 500
        assert _counter(store, LOGIN_KEY_PREFIX) is None

    def test_a_crash_during_a_password_change_leaves_the_counter_alone(self, client, store):
        """
        GIVEN a password change whose current-password check crashes
        WHEN the request is sent
        THEN the answer is a 500 and the current-password counter is untouched
        """
        token = register_and_login(client, "crash-change@example.com")
        failing = TestClient(client.app, raise_server_exceptions=False)

        with _verification_raises("verify_current_password", RuntimeError("boom")):
            response = _change(failing, token, DEFAULT_TEST_PASSWORD)

        assert response.status_code == 500
        assert _counter(store, RECONFIRM_KEY_PREFIX) is None

    def test_a_wrong_current_password_counts_once(self, client, store):
        """
        GIVEN a signed-in account
        WHEN it sends a wrong current password
        THEN the answer is 400 and the counter reads one
        """
        token = register_and_login(client, "wrong-change@example.com")

        assert _change(client, token, WRONG_PASSWORD).status_code == 400

        assert _counter(store, RECONFIRM_KEY_PREFIX) == 1


class TestActivationReservation:
    """Activation reserves on the token's counter and only records on the login one."""

    def test_a_mismatch_adds_one_to_both_counters(self, client, store, pending_account):
        """
        GIVEN a live activation token
        WHEN a wrong password is sent with it
        THEN the answer is 403 and the activation and login counters both read one
        """
        token, _password = pending_account

        assert _activate(client, token, WRONG_PASSWORD).status_code == 403

        assert _counter(store, ACTIVATION_KEY_PREFIX) == 1
        assert _counter(store, LOGIN_KEY_PREFIX) == 1

    def test_a_locked_login_counter_does_not_block_activation(self, client, store, pending_account):
        """
        GIVEN a login counter already at the limit for the account
        WHEN the right password is sent with the live token
        THEN the account activates, and both counters are cleared
        """
        token, password = pending_account
        login = RedisLoginThrottle(store, key_prefix=LOGIN_KEY_PREFIX)
        for _ in range(MAX_FAILURES):
            login.record_failure("pending@example.com")
        assert login.is_locked("pending@example.com") is True

        assert _activate(client, token, password).status_code == 200

        assert _counter(store, LOGIN_KEY_PREFIX) is None
        assert _counter(store, ACTIVATION_KEY_PREFIX) is None

    def test_the_eleventh_mismatch_is_refused_and_adds_nothing(
        self, client, store, pending_account
    ):
        """
        GIVEN a token that has taken the budget of wrong passwords
        WHEN one more arrives
        THEN it is refused with 429 and neither counter moves
        """
        token, _password = pending_account
        for _ in range(MAX_FAILURES):
            assert _activate(client, token, WRONG_PASSWORD).status_code == 403
        assert _counter(store, ACTIVATION_KEY_PREFIX) == MAX_FAILURES
        assert _counter(store, LOGIN_KEY_PREFIX) == MAX_FAILURES

        assert _activate(client, token, WRONG_PASSWORD).status_code == 429

        assert _counter(store, ACTIVATION_KEY_PREFIX) == MAX_FAILURES
        assert _counter(store, LOGIN_KEY_PREFIX) == MAX_FAILURES
