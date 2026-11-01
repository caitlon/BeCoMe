"""Integration tests for the default rate limits on the real application.

The app is built by ``api.main.create_app()`` with the limiter switched on. Every route counts
``20/second`` and ``300/minute`` per client address and request path, before the route's other
dependencies, and a route's own ``@limiter.limit`` applies on top.

A fixed window can split a burst, so these tests assert that a 429 shows up, that the requests
before the first one had the expected status, and never an exact count of 429s.
"""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session

from api.config import get_settings
from api.db.session import get_session
from api.dependencies import get_turnstile_verifier
from api.exceptions import TurnstileVerificationError
from api.main import create_app
from api.middleware.rate_limit import build_limiter, limiter

ADDRESS = "203.0.113.5"
OTHER_ADDRESS = "198.51.100.7"
CALCULATE_URL = "/api/v1/calculate"
HEALTH_URL = "/api/v1/health"
SIGNED_IN_ONLY_URLS = ["/api/v1/auth/me", "/api/v1/projects", "/api/v1/users/me"]
BURST = 70
WRONG_PASSWORD = "wrong-password"  # pragma: allowlist secret


class _AcceptingVerifier:
    """A bot check that lets every request through."""

    async def verify(self, token: str | None, *, action: str, client_ip: str) -> None:
        """Accept the request."""


class _RefusingVerifier:
    """A bot check that refuses every request."""

    async def verify(self, token: str | None, *, action: str, client_ip: str) -> None:
        """Refuse the request.

        :raises TurnstileVerificationError: Always.
        """
        raise TurnstileVerificationError("refused by the test stub")


@pytest.fixture
def app(test_engine, monkeypatch) -> FastAPI:
    """The real application, on the shared in-memory database and with the bot check stubbed.

    The lifespan's own database setup is replaced so parallel workers never share a file.
    """
    monkeypatch.setattr("api.main.create_db_and_tables", lambda: None)
    monkeypatch.setattr("api.main.warm_up_connection_pool", lambda: None)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[get_turnstile_verifier] = _AcceptingVerifier
    return application


@pytest.fixture
def limiter_on():
    """Switch the shared limiter on with empty counters; restore it afterwards."""
    previous = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
        limiter.enabled = previous


@pytest.fixture
def client(app: FastAPI, limiter_on: None):
    """A client that starts the app's lifespan and connects from ``ADDRESS``."""
    with TestClient(app, client=(ADDRESS, 50000)) as test_client:
        yield test_client


def _statuses(responses: list[Response]) -> list[int]:
    return [response.status_code for response in responses]


def _first_429(responses: list[Response]) -> int:
    """Return the index of the first 429, failing the test when there is none."""
    statuses = _statuses(responses)
    assert 429 in statuses, f"no 429 in {len(statuses)} requests"
    return statuses.index(429)


def _get_many(client: TestClient, url: str, count: int = BURST, **kwargs) -> list[Response]:
    return [client.get(url, **kwargs) for _ in range(count)]


class TestSignedInRoutes:
    """Routes behind sign-in count the default limits per client address."""

    @pytest.mark.parametrize("url", SIGNED_IN_ONLY_URLS)
    def test_an_unauthenticated_burst_is_refused_with_a_wait(self, client: TestClient, url: str):
        """
        GIVEN the real app with the limiter on
        WHEN one address sends 70 unauthenticated requests to a signed-in route
        THEN they answer 401 until a 429 with an integer Retry-After and security headers
        """
        responses = _get_many(client, url)

        first = _first_429(responses)
        assert first > 0
        assert set(_statuses(responses[:first])) == {401}
        refused = responses[first]
        assert int(refused.headers["Retry-After"]) >= 1
        assert refused.headers["X-Content-Type-Options"] == "nosniff"

    def test_the_refusal_carries_the_cors_headers(self, client: TestClient):
        """
        GIVEN a request from a configured CORS origin that is over the limit
        WHEN the 429 comes back
        THEN it carries access-control-allow-origin, so the browser lets the SPA read it
        """
        origin = get_settings().cors_origins[0]

        responses = _get_many(client, "/api/v1/auth/me", headers={"Origin": origin})

        refused = responses[_first_429(responses)]
        assert refused.headers["access-control-allow-origin"] == origin

    def test_a_calculation_without_a_token_is_counted(self, client: TestClient):
        """
        GIVEN the standalone calculation, which has a limit of its own
        WHEN one address posts 70 requests without a token
        THEN they answer 401 until a 429
        """
        body = {"experts": [{"name": "Solo", "lower": 10.0, "peak": 20.0, "upper": 30.0}]}

        responses = [client.post(CALCULATE_URL, json=body) for _ in range(BURST)]

        first = _first_429(responses)
        assert first > 0
        assert set(_statuses(responses[:first])) == {401}


class TestRoutesWithOwnLimits:
    """A route's own limit still applies, and the defaults count before the bot check."""

    def test_login_is_refused_by_its_own_limit(self, client: TestClient):
        """
        GIVEN the login route with a limit of 5 per minute
        WHEN one address tries ten different accounts
        THEN the 6th attempt at the latest is a 429 naming that limit
        """
        responses = [
            client.post(
                "/api/v1/auth/login",
                data={"username": f"nobody{i}@example.com", "password": WRONG_PASSWORD},
            )
            for i in range(10)
        ]

        first = _first_429(responses)
        assert first <= 5
        assert "5 per 1 minute" in responses[first].text

    def test_forgot_password_is_refused_by_its_own_limit(self, client: TestClient):
        """
        GIVEN the async forgot-password route with a limit of 3 per minute
        WHEN one address asks for ten resets
        THEN the 4th request at the latest is a 429 naming that limit
        """
        responses = [
            client.post("/api/v1/auth/forgot-password", json={"email": f"nobody{i}@example.com"})
            for i in range(10)
        ]

        first = _first_429(responses)
        assert first <= 3
        assert "3 per 1 minute" in responses[first].text

    def test_the_default_limit_counts_before_the_bot_check(self, app: FastAPI, client: TestClient):
        """
        GIVEN a bot check that refuses every login
        WHEN one address sends 70 logins
        THEN the refusals (403) end in a 429 naming the 20 per second default
        """
        app.dependency_overrides[get_turnstile_verifier] = _RefusingVerifier

        responses = [
            client.post(
                "/api/v1/auth/login",
                data={"username": "nobody@example.com", "password": WRONG_PASSWORD},
            )
            for _ in range(BURST)
        ]

        first = _first_429(responses)
        assert first > 0
        assert set(_statuses(responses[:first])) == {403}
        assert "20 per 1 second" in responses[first].text


class TestWhatIsNotCounted:
    """Requests that never reach the dependency, and the exempt route, count nothing."""

    def test_health_counts_nothing(self, client: TestClient):
        """
        GIVEN the health route, which is exempt
        WHEN 100 requests arrive
        THEN all answer 200 and the limiter's storage is never hit
        """
        with patch.object(limiter.limiter, "hit", wraps=limiter.limiter.hit) as hit:
            responses = _get_many(client, HEALTH_URL, 100)

        assert set(_statuses(responses)) == {200}
        hit.assert_not_called()

    def test_an_unknown_path_counts_nothing(self, client: TestClient):
        """
        GIVEN a path no route serves
        WHEN 40 requests arrive
        THEN all answer 404 and the limiter's storage is never hit
        """
        with patch.object(limiter.limiter, "hit", wraps=limiter.limiter.hit) as hit:
            responses = _get_many(client, "/api/v1/no-such-route", 40)

        assert set(_statuses(responses)) == {404}
        hit.assert_not_called()

    def test_a_malformed_body_is_refused_before_it_is_counted(self, client: TestClient):
        """
        GIVEN a JSON route and a body that is not JSON
        WHEN 40 such requests arrive
        THEN all answer 422, because FastAPI refuses the body before any dependency runs
        """
        responses = [
            client.post(CALCULATE_URL, content=b"{", headers={"Content-Type": "application/json"})
            for _ in range(40)
        ]

        assert set(_statuses(responses)) == {422}

    def test_a_disabled_limiter_counts_nothing(self, client: TestClient):
        """
        GIVEN the limiter switched off
        WHEN 100 requests arrive
        THEN none is a 429
        """
        limiter.enabled = False

        responses = _get_many(client, "/api/v1/auth/me", 100)

        assert 429 not in _statuses(responses)


class TestScopeOfTheCount:
    """The count is per client address and per request path."""

    def test_distinct_photo_urls_have_their_own_counts(self, client: TestClient):
        """
        GIVEN the public photo route, loaded once per member by a page
        WHEN one address fetches 50 different users' photos
        THEN none is a 429
        """
        responses = [client.get(f"/api/v1/users/{uuid4()}/photo") for _ in range(50)]

        assert 429 not in _statuses(responses)

    def test_one_photo_url_is_counted(self, client: TestClient):
        """
        GIVEN one photo URL
        WHEN one address fetches it 70 times
        THEN a 429 shows up
        """
        responses = _get_many(client, f"/api/v1/users/{uuid4()}/photo")

        _first_429(responses)

    def test_a_few_paths_once_each_are_not_refused(self, client: TestClient):
        """
        GIVEN seven different paths
        WHEN one address requests each once
        THEN none is a 429
        """
        urls = [*SIGNED_IN_ONLY_URLS, HEALTH_URL, "/api/v1/auth/refresh", "/api/v1/invitations"]
        urls.append(f"/api/v1/users/{uuid4()}/photo")

        responses = [client.get(url) for url in urls]

        assert len(urls) == 7
        assert 429 not in _statuses(responses)

    def test_another_address_is_unaffected(self, app: FastAPI, client: TestClient):
        """
        GIVEN one address that has used up its allowance on a path
        WHEN a second address requests the same path
        THEN it is not refused
        """
        _first_429(_get_many(client, "/api/v1/auth/me"))

        other = TestClient(app, client=(OTHER_ADDRESS, 50000))
        response = other.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestStorageOutage:
    """With the Redis store unreachable the default limits fall back to memory."""

    def test_requests_are_still_answered(self, app: FastAPI, client: TestClient):
        """
        GIVEN a limiter whose Redis store refuses connections
        WHEN requests arrive on the default-limit path
        THEN none is a 5xx, health stays 200, and the limiter has switched to its fallback
        """
        settings = SimpleNamespace(testing=False, redis_url="redis://127.0.0.1:1")
        broken = build_limiter(settings)
        app.state.limiter = broken
        limiter.enabled = False  # the routes' own limits use the module-level limiter

        responses = _get_many(client, "/api/v1/auth/me", 10)
        health = client.get(HEALTH_URL)

        assert max(_statuses(responses)) < 500
        assert health.status_code == 200
        assert broken._storage_dead is True
