"""The real app refuses a request that lacks the Cloudflare origin secret on a deployed service."""

import logging
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from api.assistant.client import UserApiClient
from api.assistant.errors import AssistantUpstreamError
from api.auth.revocation_store import get_revocation_store
from api.middleware.body_size import DEFAULT_MAX_BODY_BYTES
from api.middleware.origin_lock import OriginLockMiddleware
from tests.shared.helpers import captured_log_records

_SECRET = "an-origin-verify-secret"  # pragma: allowlist secret
_PREVIOUS_SECRET = "the-previous-origin-secret"  # pragma: allowlist secret
_WRONG = "not-the-origin-secret"  # pragma: allowlist secret
_ORIGIN = "https://app.example.com"

_HEALTH = "/api/v1/health"
_PROTECTED = "/api/v1/auth/me"
_UNROUTED = "/no/route/serves/this"

_PROBE_HOSTS = ["healthcheck.railway.app", "localhost", "healthcheck.railway.app:8000"]

AppBuilder = Callable[..., TestClient]


@pytest.fixture
def build_app(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[AppBuilder]:
    """Yield a function that builds the real ``create_app()`` under a chosen profile.

    :param monkeypatch: pytest monkeypatch fixture.
    :param tmp_path: Directory to run in, away from the repository .env.
    :return: Builder taking the profile (``prod``, ``test`` or ``dev``), the environment
        variables to add or override (``None`` removes one), and whether to expect a
        deployed service.
    """
    from api.config import get_settings
    from api.main import create_app

    def build(profile: str = "prod", *, deployed: bool = True, **env: str | None) -> TestClient:
        monkeypatch.chdir(tmp_path)
        values: dict[str, str | None] = {
            "APP_ENV": profile,
            "SECRET_KEY": "a-sufficiently-strong-secret-value",  # pragma: allowlist secret
            "DATABASE_URL": "postgresql://user:pass@host:5432/db",  # pragma: allowlist secret
            "REDIS_URL": "redis://localhost:6379/0",
            "CLOUDFLARE_ORIGIN_SECRET": _SECRET,
            "CORS_ORIGINS": f'["{_ORIGIN}"]',
            "FRONTEND_BASE_URL": _ORIGIN,
            "EMAIL_PROVIDER": "http",
            "EMAIL_API_KEY": "a-resend-api-key",  # pragma: allowlist secret
            "MIGRATION_DATABASE_URL": "postgresql://migrator:pass@host:5432/db",  # pragma: allowlist secret
            "TURNSTILE_ENABLED": "true",
            "TURNSTILE_SECRET_KEY": "a-turnstile-secret",  # pragma: allowlist secret
            "TURNSTILE_HOSTNAMES": '["app.example.com"]',
            # The test runner sets TESTING=1; only the prod profile counts as a deploy
            # while it is set. The other two profiles are the real deploys, as on Railway.
            "TESTING": None,
            "RAILWAY_ENVIRONMENT_NAME": "dev" if profile == "dev" and deployed else None,
            "CLOUDFLARE_ORIGIN_SECRET_PREVIOUS": None,
        }
        values.update(env)
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        assert get_settings().is_deploy is deployed
        return TestClient(create_app(), base_url="https://api.example.com")

    try:
        yield build
    finally:
        get_settings.cache_clear()
        # A route with sign-in builds this process-wide store from the settings above, and
        # a store pointing at this Redis URL would break every later test in the process.
        get_revocation_store.cache_clear()


@pytest.fixture(params=["prod", "test", "dev"])
def deployed_client(request: pytest.FixtureRequest, build_app: AppBuilder) -> TestClient:
    """Return a client on the real app under each of the three deploy profiles."""
    return build_app(request.param)


class TestRefusal:
    """A request without the secret gets a 403 on every path."""

    @pytest.mark.parametrize("path", [_HEALTH, _PROTECTED, _UNROUTED])
    def test_request_without_the_secret_is_refused(
        self, deployed_client: TestClient, path: str
    ) -> None:
        """
        GIVEN a deployed service
        WHEN a request lacks X-Origin-Verify
        THEN it is refused with a JSON 403 that Cloudflare may not cache
        """
        # WHEN
        response = deployed_client.get(path)

        # THEN
        assert response.status_code == 403
        assert response.json() == {"detail": "Forbidden"}
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-request-id"]

    @pytest.mark.parametrize("value", [_WRONG, "", _PREVIOUS_SECRET])
    def test_wrong_value_is_refused(self, deployed_client: TestClient, value: str) -> None:
        """
        GIVEN a deployed service with no previous secret
        WHEN X-Origin-Verify is wrong, empty or a value that is not configured
        THEN the request is refused
        """
        response = deployed_client.get(_PROTECTED, headers={"X-Origin-Verify": value})

        assert response.status_code == 403

    def test_non_ascii_value_is_refused_not_a_server_error(
        self, deployed_client: TestClient
    ) -> None:
        """
        GIVEN a deployed service
        WHEN X-Origin-Verify carries bytes outside ASCII
        THEN the request is refused with a 403, not a 500
        """
        headers = {"X-Origin-Verify": "secrét".encode("latin-1")}

        response = deployed_client.get(_PROTECTED, headers=headers)

        assert response.status_code == 403

    def test_right_value_passes(self, deployed_client: TestClient) -> None:
        """GIVEN a deployed service WHEN the request carries the secret THEN it is served."""
        response = deployed_client.get(_HEALTH, headers={"X-Origin-Verify": _SECRET})

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRotation:
    """During a rotation the previous secret is accepted next to the current one."""

    def test_previous_value_is_accepted(self, build_app: AppBuilder) -> None:
        """
        GIVEN a deployed service with a previous secret set
        WHEN a request carries the previous value
        THEN it is served
        """
        client = build_app(CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_PREVIOUS_SECRET)

        response = client.get(_HEALTH, headers={"X-Origin-Verify": _PREVIOUS_SECRET})

        assert response.status_code == 200

    def test_current_value_is_still_accepted(self, build_app: AppBuilder) -> None:
        """
        GIVEN a deployed service with a previous secret set
        WHEN a request carries the current value
        THEN it is served
        """
        client = build_app(CLOUDFLARE_ORIGIN_SECRET_PREVIOUS=_PREVIOUS_SECRET)

        response = client.get(_HEALTH, headers={"X-Origin-Verify": _SECRET})

        assert response.status_code == 200

    def test_previous_value_is_refused_when_not_configured(self, build_app: AppBuilder) -> None:
        """
        GIVEN a deployed service with no previous secret
        WHEN a request carries what used to be the previous value
        THEN it is refused
        """
        client = build_app()

        response = client.get(_HEALTH, headers={"X-Origin-Verify": _PREVIOUS_SECRET})

        assert response.status_code == 403

    def test_empty_header_is_refused_with_an_empty_previous_value(
        self, build_app: AppBuilder
    ) -> None:
        """
        GIVEN a deployed service whose previous secret is the empty string
        WHEN a request carries an empty X-Origin-Verify
        THEN it is refused, so an unset previous value never matches
        """
        client = build_app(CLOUDFLARE_ORIGIN_SECRET_PREVIOUS="")

        response = client.get(_HEALTH, headers={"X-Origin-Verify": ""})

        assert response.status_code == 403


class TestPlatformProbe:
    """Only the health route, addressed to a probe's host name, passes without the secret."""

    @pytest.mark.parametrize("host", _PROBE_HOSTS)
    def test_health_probe_is_served(self, deployed_client: TestClient, host: str) -> None:
        """
        GIVEN a deployed service
        WHEN GET /api/v1/health arrives without the secret under a probe's host name
        THEN it is served
        """
        response = deployed_client.get(_HEALTH, headers={"Host": host})

        assert response.status_code == 200

    @pytest.mark.parametrize("host", _PROBE_HOSTS)
    def test_probe_host_does_not_open_other_routes(
        self, deployed_client: TestClient, host: str
    ) -> None:
        """
        GIVEN a deployed service
        WHEN another route is called under a probe's host name without the secret
        THEN it is refused
        """
        response = deployed_client.get(_PROTECTED, headers={"Host": host})

        assert response.status_code == 403

    def test_probe_host_does_not_open_other_methods(self, deployed_client: TestClient) -> None:
        """GIVEN a deployed service WHEN a probe host POSTs to health THEN it is refused."""
        response = deployed_client.post(_HEALTH, headers={"Host": "healthcheck.railway.app"})

        assert response.status_code == 403

    def test_other_host_on_health_is_refused(self, deployed_client: TestClient) -> None:
        """GIVEN a deployed service WHEN health is called under a custom host THEN it is refused."""
        response = deployed_client.get(_HEALTH, headers={"Host": "api.example.com"})

        assert response.status_code == 403


class TestCors:
    """The lock sits inside CORS: a preflight is answered there, a refusal stays readable."""

    def test_preflight_is_answered_by_cors(self, deployed_client: TestClient) -> None:
        """
        GIVEN a deployed service
        WHEN the browser sends a CORS preflight without the secret
        THEN CORS answers it and the lock logs no refusal
        """
        headers = {"Origin": _ORIGIN, "Access-Control-Request-Method": "POST"}

        with captured_log_records("api.request") as records:
            response = deployed_client.options(_PROTECTED, headers=headers)

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == _ORIGIN
        assert [r for r in records if getattr(r, "event", None) == "origin_refused"] == []

    def test_plain_options_is_refused(self, deployed_client: TestClient) -> None:
        """
        GIVEN a deployed service
        WHEN an OPTIONS request is not a preflight
        THEN it is refused
        """
        response = deployed_client.options(_PROTECTED, headers={"Origin": _ORIGIN})

        assert response.status_code == 403

    def test_refusal_carries_the_cors_headers(self, deployed_client: TestClient) -> None:
        """
        GIVEN a deployed service
        WHEN a cross-origin GET without the secret is refused
        THEN the 403 still names the allowed origin, so the SPA can read it
        """
        response = deployed_client.get(_PROTECTED, headers={"Origin": _ORIGIN})

        assert response.status_code == 403
        assert response.headers["access-control-allow-origin"] == _ORIGIN


def test_refusal_comes_before_the_body_size_check(deployed_client: TestClient) -> None:
    """
    GIVEN a deployed service
    WHEN a body above the JSON limit arrives without the secret
    THEN the answer is 403, so the guard behind the lock never sees the body
    """
    body = b"x" * (DEFAULT_MAX_BODY_BYTES + 16)

    response = deployed_client.post(
        "/api/v1/calculate", content=body, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 403


class TestLogging:
    """A refusal is logged without the value that was sent or the real secret."""

    @staticmethod
    def _refusals(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
        return [r for r in records if getattr(r, "event", None) == "origin_refused"]

    @pytest.mark.parametrize(
        ("headers", "reason"),
        [({}, "missing_header"), ({"X-Origin-Verify": _WRONG}, "secret_mismatch")],
    )
    def test_refusal_record(
        self, deployed_client: TestClient, headers: dict[str, str], reason: str
    ) -> None:
        """
        GIVEN a deployed service
        WHEN a request is refused
        THEN one WARNING names the reason and the unverified address, and no field of any
            record holds the value that was sent or the real secret
        """
        with captured_log_records("api.request") as records:
            deployed_client.get(_PROTECTED, headers=headers)

        refusals = self._refusals(records)
        assert len(refusals) == 1
        record = refusals[0]
        assert record.levelno == logging.WARNING
        assert record.getMessage() == "Request refused: origin not verified"
        assert record.reason == reason  # type: ignore[attr-defined]
        assert record.ip == "unverified-origin"  # type: ignore[attr-defined]
        assert record.method == "GET"  # type: ignore[attr-defined]
        assert record.path == _PROTECTED  # type: ignore[attr-defined]
        assert record.request_id  # type: ignore[attr-defined]
        for logged in records:
            assert all(_WRONG not in str(v) for v in logged.__dict__.values())
            assert all(_SECRET not in str(v) for v in logged.__dict__.values())
            assert _WRONG not in logged.getMessage()
            assert _SECRET not in logged.getMessage()

    def test_access_line_reports_the_refusal(self, deployed_client: TestClient) -> None:
        """
        GIVEN a deployed service
        WHEN a non-health request is refused
        THEN the request log reports status 403 and its start line the unverified address
        """
        with captured_log_records("api.request") as records:
            deployed_client.get(_PROTECTED)

        statuses = [getattr(r, "status_code", None) for r in records]
        ips = [getattr(r, "ip", None) for r in records if getattr(r, "method", None)]
        assert 403 in statuses
        assert ips and set(ips) == {"unverified-origin"}


class TestOffADeploy:
    """On a laptop or in CI nothing changes."""

    def test_no_lock_and_no_header_needed(self, build_app: AppBuilder) -> None:
        """
        GIVEN the dev profile with no Railway marker and an origin secret set
        WHEN a request carries no secret
        THEN it is served and the middleware is not on the app
        """
        client = build_app("dev", deployed=False)

        response = client.get(_HEALTH)

        assert response.status_code == 200
        assert OriginLockMiddleware not in [m.cls for m in client.app.user_middleware]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_in_process_client_passes_the_lock(build_app: AppBuilder) -> None:
    """
    GIVEN a deployed app
    WHEN UserApiClient calls a path the probe exemption does not cover
    THEN the secret it sends gets the call through to the route, which answers 401, not 403

    The health path is exempt from the lock, so it would pass without the header. The
    protected path is refused 403 by the lock without it, and answered 401 by the route
    for the fake token with it.
    """
    app = build_app().app
    api_client = UserApiClient(app=app, access_token="a-token", client_ip="203.0.113.7")

    try:
        with pytest.raises(AssistantUpstreamError) as excinfo:
            await api_client._get_json(_PROTECTED)
    finally:
        await api_client.aclose()

    assert "returned 401" in str(excinfo.value)
