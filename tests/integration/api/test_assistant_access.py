"""Integration tests that pin who the assistant acts as, and what it may read for them.

The chat model is always a scripted one from ``tests/shared/assistant_fakes.py``, the
retriever is the static one the shared test app installs, and the API the assistant reads
from is the test app itself. Nothing here reaches a real model server, embedding server or
vector database.

The tests cover three things: the session that opens each route (the 401 matrix, the CSRF
token of another session, a cookie that wins over a bearer token), what happens when that
session ends in the middle of a turn, and the shape of the requests the assistant's own
client sends back into the application.
"""

import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlmodel import Session

from api.assistant import deps
from api.assistant.client import UserApiClient
from api.assistant.exception_handlers import UNAVAILABLE_DETAIL
from api.auth.cookies import CSRF_COOKIE
from api.auth.jwt import create_access_token, decode_token
from api.auth.revocation_store import get_revocation_store
from api.config import get_settings
from api.db.session import get_session
from api.middleware.origin_lock import OriginLockMiddleware
from tests.integration.api import test_assistant_chat as chat_tests
from tests.integration.api.conftest import (
    create_project,
    create_test_app,
    register_and_login,
    stored_accounts,
)
from tests.integration.api.test_assistant_chat import (
    CHAT,
    OWNER_PROJECT,
    OWNER_SECRETS,
    STREAM,
    UNAVAILABLE_BODY,
    _events,
    _owner_project,
    _scripted,
    _shown,
    _sign_in_with_cookies,
    _sign_in_with_cookies_again,
    _tool_call,
    _use_model,
)
from tests.shared.assistant_fakes import ScriptedToolCallingModel, ToolEchoingModel
from tests.shared.assistant_probe_fakes import (
    HookedEchoModel,
    record_inner_requests,
    tool_call_of,
)
from tests.shared.helpers import auth_header, mock_datetime_offset

# The chat tests' fixtures, reused as they are: ``_chat_settings`` gives every test explicit
# settings and empty caches (it applies to this module once it is named here), and
# ``configure`` changes settings in the middle of a test.
_chat_settings = chat_tests._chat_settings
configure = chat_tests.configure

CONFIG = "/api/v1/assistant/config"
_ROUTES = [("GET", CONFIG), ("POST", CHAT), ("POST", STREAM)]
_ROUTE_IDS = ["config", "chat", "stream"]
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

# Names that exist only in one account's project, so that the other account's answer can be
# searched for them.
_ALPHA_EMAIL = "alpha@example.com"
_BRAVO_EMAIL = "bravo@example.com"
_ALPHA_PROJECT = "Kestrel Harbour Survey"
_BRAVO_PROJECT = "Quokka Meadow Census"

# The value the origin lock is configured with in the tests of the inner read.
_ORIGIN_SECRET = "origin-secret-5c1e9a07"  # pragma: allowlist secret


def _send(client: TestClient, method: str, path: str, headers: dict[str, str]) -> Any:
    """Send a request to an assistant route with a body that is valid on the chat routes."""
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json={"message": "hi"}, headers=headers)


def _answer_of(response: Any, endpoint: str) -> str:
    """Return the answer text of a chat response, or of the done event of a stream."""
    if endpoint == CHAT:
        return str(response.json()["answer"])
    name, payload = _events(response.text)[-1]
    assert name == "done"
    return str(payload["answer"])


class _OneHourAhead(datetime):
    """A ``datetime`` whose ``now`` reads one hour later, for PyJWT's expiry check."""

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "_OneHourAhead":
        return cls.fromtimestamp(time.time() + 3600, tz)


def _let_access_tokens_expire(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Return a function that moves the clock PyJWT checks ``exp`` against one hour ahead.

    PyJWT reads the time in ``jwt.api_jwt``, a module the application's own clock helpers
    do not touch, so only the validation of a token sees the jump: tokens are still minted
    and compared to their database rows on the real clock. The patch lasts for the test.
    After the jump PyJWT's ``encode`` cannot mint a token (the patched ``datetime`` breaks
    its ``isinstance`` check), so every token a test needs is minted before the jump.
    """

    def jump() -> None:
        monkeypatch.setattr(jwt.api_jwt, "datetime", _OneHourAhead)

    return jump


class TestNoValidSessionIs401:
    """Every assistant route refuses a request without a usable session, before any model call."""

    @staticmethod
    def _credentials(kind: str, client: TestClient) -> dict[str, str]:
        """Build the headers of one kind of bad (or absent) session for an existing account."""
        email = "session@example.com"
        token = register_and_login(client, email)
        if kind == "none":
            return {}
        if kind == "garbage":
            return auth_header("garbage")
        if kind == "revoked":
            assert client.get(CONFIG, headers=auth_header(token)).status_code == 200
            store = get_revocation_store()
            store.revoke_jti(decode_token(token, "access", store).jti, 900)
            return auth_header(token)
        user_id = stored_accounts(client, email)[0]["id"]
        with mock_datetime_offset("api.auth.jwt.datetime", timedelta(hours=1)):
            return auth_header(create_access_token(user_id))

    @pytest.mark.parametrize("kind", ["none", "garbage", "revoked", "expired"])
    @pytest.mark.parametrize(("method", "path"), _ROUTES, ids=_ROUTE_IDS)
    def test_a_request_without_a_valid_session_is_401_and_asks_no_model(
        self, assistant_settings, client, method, path, kind
    ):
        """
        GIVEN a registered account, and each of four ways of presenting no valid session:
            no token, a token nobody issued, a revoked token and an expired one
        WHEN the config route, the chat route and the stream route are each requested so
        THEN the answer is 401 and the scripted model was never asked
        """
        # GIVEN
        headers = self._credentials(kind, client)
        model = _scripted("never used")
        _use_model(client, model)

        # WHEN
        response = _send(client, method, path, headers)

        # THEN
        assert response.status_code == 401
        assert model.seen == []

    @pytest.mark.parametrize(("method", "path"), _ROUTES, ids=_ROUTE_IDS)
    def test_a_valid_token_is_answered_on_every_route(
        self, assistant_settings, client, method, path
    ):
        """
        GIVEN the account of the cases above with a token that is valid
        WHEN the same three routes are requested
        THEN each is answered 200, so the 401s above are about the session and nothing else
        """
        # GIVEN
        token = register_and_login(client, "session@example.com")
        _use_model(client, _scripted("A fuzzy compromise."))

        # WHEN
        response = _send(client, method, path, auth_header(token))

        # THEN
        assert response.status_code == 200


class TestCsrfTokenOfAnotherSession:
    """A cookie session is only good with the CSRF token derived from that same session."""

    @pytest.mark.parametrize("endpoint", [CHAT, STREAM])
    @pytest.mark.parametrize("other", ["another account", "the same account, another session"])
    def test_the_csrf_token_of_another_session_is_403_and_asks_no_model(
        self, assistant_settings, cookie_client, endpoint, other
    ):
        """
        GIVEN two signed-in cookie sessions on one application, each with its own CSRF token,
            the second of another account or of the same account
        WHEN a request carries the first session's cookie and the second session's token,
            in the header and in the CSRF cookie alike
        THEN the answer is 403 with the code csrf_invalid and no model was asked
            AND the first session's own token is answered (the control)
        """
        # GIVEN
        csrf_a = _sign_in_with_cookies(cookie_client, "csrf-a@example.com")
        other_client = TestClient(cookie_client.app, base_url="https://testserver")
        if other == "another account":
            csrf_b = _sign_in_with_cookies(other_client, "csrf-b@example.com")
        else:
            csrf_b = _sign_in_with_cookies_again(other_client, "csrf-a@example.com")
        assert csrf_a != csrf_b
        model = _scripted("never used", "Answered.")
        _use_model(cookie_client, model)

        # WHEN
        # The CSRF cookie holds the other session's value too, so a check that only compared
        # the header with the cookie would let this request through.
        own_cookie = cookie_client.cookies.get(CSRF_COOKIE)
        cookie_client.cookies.set(CSRF_COOKIE, csrf_b["X-CSRF-Token"])
        refused = cookie_client.post(endpoint, json={"message": "hi"}, headers=csrf_b)
        cookie_client.cookies.set(CSRF_COOKIE, own_cookie)
        own = cookie_client.post(endpoint, json={"message": "hi"}, headers=csrf_a)

        # THEN
        assert refused.status_code == 403
        assert refused.json()["code"] == "csrf_invalid"
        assert own.status_code == 200
        assert len(model.seen) == 1


class TestCookieOutranksBearer:
    """When a request carries both a session cookie and a bearer token, the cookie is the caller."""

    @pytest.mark.parametrize("endpoint", [CHAT, STREAM])
    def test_the_cookie_owner_is_read_and_charged_and_the_bearer_owner_is_not(
        self, assistant_settings, cookie_client, configure, endpoint
    ):
        """
        GIVEN two accounts with a project each, an hourly budget of one message, and a
            request with the cookie of the first and the bearer token of the second
        WHEN the model lists the projects of the caller
        THEN the list holds the first account's project and never the second's
            AND afterwards the second account alone is answered, because its budget is
            untouched, and the first account alone is refused with 429, because it paid
        """
        # GIVEN
        configure(ASSISTANT_MODE="agent", ASSISTANT_RATE_LIMIT_PER_HOUR="1")
        token_alpha = register_and_login(cookie_client, _ALPHA_EMAIL)
        create_project(cookie_client, token_alpha, name=_ALPHA_PROJECT)
        token_bravo = register_and_login(cookie_client, _BRAVO_EMAIL)
        create_project(cookie_client, token_bravo, name=_BRAVO_PROJECT)
        csrf_alpha = _sign_in_with_cookies_again(cookie_client, _ALPHA_EMAIL)
        model = ToolEchoingModel(first_call=tool_call_of("list_my_projects", {}))
        _use_model(cookie_client, model)

        # WHEN
        mixed = cookie_client.post(
            endpoint,
            json={"message": "Which projects?"},
            headers={**csrf_alpha, **auth_header(token_bravo)},
        )

        # THEN
        assert mixed.status_code == 200
        mixed_answer = _answer_of(mixed, endpoint)
        assert _ALPHA_PROJECT in mixed_answer
        assert _BRAVO_PROJECT not in mixed_answer
        assert _BRAVO_PROJECT not in _shown(model)

        # WHEN the two accounts ask on their own
        _use_model(cookie_client, _scripted("Bravo is answered."))
        cookie_client.cookies.clear()
        bravo_alone = cookie_client.post(
            endpoint, json={"message": "hi"}, headers=auth_header(token_bravo)
        )
        _use_model(cookie_client, _scripted("never used"))
        csrf_alpha = _sign_in_with_cookies_again(cookie_client, _ALPHA_EMAIL)
        alpha_alone = cookie_client.post(endpoint, json={"message": "hi"}, headers=csrf_alpha)

        # THEN
        assert bravo_alone.status_code == 200
        assert alpha_alone.status_code == 429


class TestSessionEndsMidTurn:
    """A session that ends while the model is thinking opens no project data afterwards."""

    @pytest.mark.parametrize("endpoint", [CHAT, STREAM])
    @pytest.mark.parametrize(
        "tool",
        ["list_my_projects", "get_project", "get_project_result", "get_project_opinions"],
    )
    @pytest.mark.parametrize("ending", ["none", "jti revoked", "session revoked"])
    def test_a_session_revoked_mid_turn_reads_nothing(
        self, assistant_settings, client, configure, tool, ending, endpoint
    ):
        """
        GIVEN the agent mode and a model that, before its first reply, ends the caller's
            session (revokes the token's id, or its whole session), then asks for the
            caller's own projects or one project through a tool; or, as the control, ends
            nothing
        WHEN the owner asks, on the chat route and on the stream route
        THEN the control reads the project, and a revoked session gets the unavailable:
            reply from the tool, with nothing of the owner's project in the answer or in
            anything the model was shown
        """
        # GIVEN
        configure(ASSISTANT_MODE="agent")
        owner = _owner_project(client)
        store = get_revocation_store()
        payload = decode_token(owner["token"], "access", store)

        def end_session() -> None:
            if ending == "jti revoked":
                store.revoke_jti(payload.jti, 900)
            elif ending == "session revoked":
                store.revoke_session(payload.sid, 900)

        first_call = (
            tool_call_of(tool, {}) if tool == "list_my_projects" else _tool_call(tool, owner["id"])
        )
        model = HookedEchoModel(first_call=first_call, before_first_call=end_session)
        _use_model(client, model)

        # WHEN
        response = client.post(
            endpoint, json={"message": "Tell me about it"}, headers=auth_header(owner["token"])
        )

        # THEN
        assert response.status_code == 200
        answer = _answer_of(response, endpoint)
        assert len(model.seen) == 2
        if ending == "none":
            assert not answer.startswith("unavailable:")
            assert any(secret in answer for secret in OWNER_SECRETS)
        else:
            assert answer.startswith("unavailable:")
            for secret in OWNER_SECRETS:
                assert secret not in answer
                assert secret not in _shown(model)

    @pytest.mark.parametrize(
        ("mode", "moment"),
        [("agent", "model call"), ("hybrid", "before the turn"), ("workflow", "before the turn")],
    )
    def test_a_token_that_expires_mid_turn_reads_nothing(
        self, assistant_settings, client, configure, monkeypatch, mode, moment
    ):
        """
        GIVEN a request that passed authentication, and the clock PyJWT checks moving past
            the token's expiry: in the agent mode just before the model's first reply, in
            the other modes before the turn reads the project it fetches ahead
        WHEN the owner asks
        THEN the agent mode's tool replies unavailable: with nothing of the project shown to
            the model, and the other modes answer 503 with the fixed body and never ask
            the model, since the project they fetch ahead cannot be read
        """
        # GIVEN
        configure(ASSISTANT_MODE=mode)
        owner = _owner_project(client)
        expire = _let_access_tokens_expire(monkeypatch)
        body: dict[str, Any] = {"message": "Tell me about it", "project_id": owner["id"]}
        if moment == "model call":
            model: ScriptedToolCallingModel | ToolEchoingModel = HookedEchoModel(
                first_call=_tool_call("get_project", owner["id"]), before_first_call=expire
            )
            _use_model(client, model)
        else:
            model = _scripted("never used")

            def model_after_the_jump() -> ScriptedToolCallingModel:
                expire()
                return model

            client.app.dependency_overrides[deps.get_answer_model] = model_after_the_jump

        # WHEN
        response = client.post(CHAT, json=body, headers=auth_header(owner["token"]))

        # THEN
        if moment == "model call":
            assert response.status_code == 200
            assert response.json()["answer"].startswith("unavailable:")
            assert len(model.seen) == 2
        else:
            assert response.status_code == 503
            assert response.json() == {"detail": UNAVAILABLE_DETAIL} == UNAVAILABLE_BODY
            assert model.seen == []
        for secret in OWNER_SECRETS:
            assert secret not in response.text
            assert secret not in _shown(model)

    def test_a_token_that_has_not_expired_reads_the_project(
        self, assistant_settings, client, configure
    ):
        """
        GIVEN the workflow mode of the case above with the clock left alone
        WHEN the owner asks with the project named
        THEN the project is shown to the model, so the 503 above is about the expiry
        """
        # GIVEN
        configure(ASSISTANT_MODE="workflow")
        owner = _owner_project(client)
        model = _scripted("It is a ledger.")
        _use_model(client, model)

        # WHEN
        response = client.post(
            CHAT,
            json={"message": "Tell me about it", "project_id": owner["id"]},
            headers=auth_header(owner["token"]),
        )

        # THEN
        assert response.status_code == 200
        assert OWNER_PROJECT in _shown(model)


class TestInnerReadsAreGetsOfTheProjectsApi:
    """What the assistant sends back into the application is a read of one of four resources."""

    def test_every_inner_request_is_a_get_of_the_projects_paths(
        self, assistant_settings, client, configure, monkeypatch
    ):
        """
        GIVEN the agent mode, a model that calls all five tools, one per reply, and a
            recorder between the assistant's client and the application
        WHEN the owner asks
        THEN the four tools that read the application produced requests, each of the four
            shapes was read, and every request is a GET of /api/v1/projects, of one project,
            of its result or of its opinions, with a UUID in the path and nothing else;
            the query holds only the paging keys and the opinions flag, and the opinions
            read asks for the assistant's view
        """
        # GIVEN
        configure(ASSISTANT_MODE="agent", ASSISTANT_MAX_TOOL_CALLS="6")
        owner = _owner_project(client)
        inner = record_inner_requests(monkeypatch)
        project_id = owner["id"]
        calls = [
            tool_call_of("list_my_projects", {}, "call_1"),
            tool_call_of("get_project", {"project_id": project_id}, "call_2"),
            tool_call_of("get_project_result", {"project_id": project_id}, "call_3"),
            tool_call_of("get_project_opinions", {"project_id": project_id}, "call_4"),
            tool_call_of("search_docs", {"query": "what is the best compromise"}, "call_5"),
        ]
        model = ScriptedToolCallingModel(responses=[*calls, AIMessage(content="Done.")])
        _use_model(client, model)

        # WHEN
        response = client.post(
            CHAT, json={"message": "Tell me everything"}, headers=auth_header(owner["token"])
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["tools_used"] == [call.tool_calls[0]["name"] for call in calls]
        assert inner
        shape = re.compile(rf"^/api/v1/projects(/{_UUID}(/(result|opinions))?)?$")
        assert {request.method for request in inner} == {"GET"}
        assert all(shape.fullmatch(request.path) for request in inner), inner
        paths = {request.path for request in inner}
        assert paths == {
            "/api/v1/projects",
            f"/api/v1/projects/{project_id}",
            f"/api/v1/projects/{project_id}/result",
            f"/api/v1/projects/{project_id}/opinions",
        }
        assert all(set(request.query) <= {"limit", "offset", "for_assistant"} for request in inner)
        opinions = [request for request in inner if request.path.endswith("/opinions")]
        assert opinions
        assert all(request.query.get("for_assistant") == ["true"] for request in opinions)

    def test_the_client_offers_exactly_four_reads_and_a_close(self):
        """
        GIVEN the assistant's API client
        WHEN its public callables are listed
        THEN they are the four reads and the close, so that no write can be added unseen
        """
        # GIVEN
        names = {
            name
            for name in dir(UserApiClient)
            if not name.startswith("_") and callable(getattr(UserApiClient, name))
        }

        # THEN
        assert names == {"list_projects", "get_project", "get_result", "get_opinions", "aclose"}


class TestInnerReadsUnderTheOriginLock:
    """The assistant's inner read carries the origin secret, which the lock refuses to go without."""

    @pytest.fixture
    def locked_client(self, assistant_settings, test_engine, configure):
        """Build a test client for an app behind the origin lock, sending the secret itself."""
        configure(ASSISTANT_MODE="agent", CLOUDFLARE_ORIGIN_SECRET=_ORIGIN_SECRET)
        app = create_test_app()
        app.add_middleware(OriginLockMiddleware)

        def override_get_session():
            with Session(test_engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        with TestClient(app, headers={"X-Origin-Verify": _ORIGIN_SECRET}) as test_client:
            yield test_client

    def test_with_the_secret_the_tool_read_succeeds(self, locked_client):
        """
        GIVEN an app behind the origin lock and a model that asks for the owner's project
        WHEN the owner asks with the secret on the outer request
        THEN the inner read carried the secret too, and the project reaches the model
        """
        # GIVEN
        owner = _owner_project(locked_client)
        model = ToolEchoingModel(first_call=_tool_call("get_project", owner["id"]))
        _use_model(locked_client, model)

        # WHEN
        response = locked_client.post(
            CHAT, json={"message": "Tell me about it"}, headers=auth_header(owner["token"])
        )

        # THEN
        assert response.status_code == 200
        assert OWNER_PROJECT in response.json()["answer"]
        assert OWNER_PROJECT in _shown(model)

    def test_without_the_secret_on_the_inner_client_the_read_is_refused(
        self, locked_client, monkeypatch
    ):
        """
        GIVEN the same app, and an assistant client that sees no origin secret in its settings
            while the application keeps it
        WHEN the owner asks
        THEN the outer request is answered, the lock refuses the inner read with 403, the tool
            replies unavailable: and nothing of the project reaches the model
        """
        # GIVEN
        owner = _owner_project(locked_client)
        real_settings = get_settings()
        monkeypatch.setattr(
            "api.assistant.client.get_settings",
            lambda: real_settings.model_copy(update={"cloudflare_origin_secret": ""}),
        )
        inner = record_inner_requests(monkeypatch)
        model = ToolEchoingModel(first_call=_tool_call("get_project", owner["id"]))
        _use_model(locked_client, model)

        # WHEN
        response = locked_client.post(
            CHAT, json={"message": "Tell me about it"}, headers=auth_header(owner["token"])
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["answer"].startswith("unavailable:")
        assert [request.path for request in inner] == [f"/api/v1/projects/{owner['id']}"]
        assert [request.status for request in inner] == [403]
        for secret in OWNER_SECRETS:
            assert secret not in response.text
            assert secret not in _shown(model)

    def test_the_lock_refuses_an_outer_request_without_the_secret(self, locked_client):
        """
        GIVEN the same app
        WHEN a request arrives without the secret
        THEN the lock answers 403 and no model is asked, so the lock really is on
        """
        # GIVEN
        owner = _owner_project(locked_client)
        model = _scripted("never used")
        _use_model(locked_client, model)
        bare_client = TestClient(locked_client.app)

        # WHEN
        response = bare_client.post(
            CHAT, json={"message": "hi"}, headers=auth_header(owner["token"])
        )

        # THEN
        assert response.status_code == 403
        assert model.seen == []
