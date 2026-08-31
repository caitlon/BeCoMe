"""E2E test fixtures: a real server and a real database."""

import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlmodel import Session, select

from api.db.engine import get_engine
from api.db.models import User
from api.db.utils import utc_now

E2E_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_PASSWORD = "SecurePass123!"

_E2E_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    """Skip the E2E tests when the run is distributed across workers.

    These tests share one uvicorn process and one database, so on more than one
    worker they queue behind each other until the ten-second client timeout in
    ``http_client`` starts firing: at twelve workers a quarter of them failed that
    way. The CI job and ``scripts/ci/e2e-local.sh`` pass ``-n 0`` for exactly that
    reason, but ``addopts`` carries ``-n logical``, so a plain ``pytest tests/``
    still sweeps this directory in at full width. Without this hook that run pays
    ten reconnect attempts per worker when the stack is down, and a cascade of
    timeouts when it is up. Skipping here states the requirement instead.

    Both halves of the check matter: ``workerinput`` exists only inside an xdist
    worker, which is where the tests would actually execute, and ``numprocesses``
    covers the controller process that collects before any worker starts.

    :param config: Active pytest configuration
    :param items: Collected test items, filtered here to this directory
    """
    distributed = hasattr(config, "workerinput") or bool(
        getattr(config.option, "numprocesses", None)
    )
    if not distributed:
        return
    skip_distributed = pytest.mark.skip(
        reason="E2E needs -n 0: the workers would share one server and one database"
    )
    for item in items:
        if _E2E_DIR in Path(str(item.fspath)).parents:
            item.add_marker(skip_distributed)


def verify_user_email(email: str) -> None:
    """Mark a registered address verified straight through the E2E database.

    Registration creates an account that cannot log in until its address is confirmed,
    and the activation token exists only inside the email the API sends, which no
    test can read. So the harness writes the column instead, connecting to the same
    database the running API uses (``DATABASE_URL``). Everything else in the flow still
    goes through the real endpoints.

    :param email: Address of an already-registered account
    """
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == email.lower())).first()
        assert user is not None, f"no account is registered for {email}"
        user.email_verified_at = utc_now()
        session.add(user)
        session.commit()


@pytest.fixture(scope="session")
def api_url():
    """Return base API URL after verifying server is running.

    Attempts to connect to health endpoint up to 10 times.
    Skips all E2E tests if the server is unreachable.

    :return: Base API URL string
    """
    for attempt in range(10):
        try:
            response = httpx.get(f"{E2E_BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                return E2E_BASE_URL
        except httpx.RequestError:
            pass
        if attempt < 9:
            time.sleep(1)
    pytest.skip("API server not running at localhost:8000")


class _HeaderOnlyClient(httpx.Client):
    """httpx client that drops response cookies after each request.

    The E2E suite authenticates with the Authorization header; discarding the session
    cookies the app now sets keeps a valid ambient cookie from overriding a Bearer token
    or tripping the CSRF check. A cookie-flow E2E test, if added, should use a plain
    ``httpx.Client`` instead.
    """

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        self.cookies.clear()
        return response


@pytest.fixture
def http_client(api_url):
    """Create a header-auth httpx client scoped to a single test (cookies not retained).

    :param api_url: Base API URL from session fixture
    :return: httpx.Client instance
    """
    with _HeaderOnlyClient(base_url=api_url, timeout=10) as client:
        yield client


def unique_email(prefix: str = "user") -> str:
    """Generate a unique email address for test isolation.

    :param prefix: Email prefix (e.g., "owner", "expert")
    :return: Unique email string
    """
    return f"{prefix}-{uuid4().hex[:12]}@e2e-test.com"


def register_user(client: httpx.Client, email: str) -> str:
    """Register a new user, activate the account, and return their access token.

    :param client: httpx.Client instance
    :param email: User email address
    :return: JWT access token string
    """
    reg_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    reg_response.raise_for_status()
    verify_user_email(email)

    response = client.post(
        "/auth/login",
        data={"username": email, "password": DEFAULT_PASSWORD},
    )
    response.raise_for_status()
    # Drop the session cookies the login set, so header-based tests authenticate purely
    # via the returned token and no ambient cookie overrides an explicit Authorization.
    client.cookies.clear()
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    """Create authorization headers from token.

    :param token: JWT access token
    :return: Headers dict with Bearer authorization
    """
    return {"Authorization": f"Bearer {token}"}


def create_project(client: httpx.Client, token: str, name: str = "E2E Project") -> dict:
    """Create a project and return its response data.

    :param client: httpx.Client instance
    :param token: Admin user's access token
    :param name: Project name
    :return: Project response dict with 'id' field
    """
    response = client.post(
        "/projects",
        json={"name": name},
        headers=auth_headers(token),
    )
    response.raise_for_status()
    return response.json()


def invite_and_accept(
    client: httpx.Client,
    owner_token: str,
    expert_token: str,
    expert_email: str,
    project_id: str,
) -> None:
    """Invite an expert to a project and accept the invitation.

    :param client: httpx.Client instance
    :param owner_token: Project owner's access token
    :param expert_token: Expert's access token
    :param expert_email: Expert's email address
    :param project_id: Project UUID string
    """
    invite_resp = client.post(
        f"/projects/{project_id}/invite",
        json={"email": expert_email},
        headers=auth_headers(owner_token),
    )
    invite_resp.raise_for_status()

    inv_resp = client.get("/invitations", headers=auth_headers(expert_token))
    inv_resp.raise_for_status()
    invitations = inv_resp.json()
    assert invitations, "No pending invitations for expert"
    invitation_id = invitations[0]["id"]

    accept_resp = client.post(
        f"/invitations/{invitation_id}/accept",
        headers=auth_headers(expert_token),
    )
    accept_resp.raise_for_status()


def register_user_with_name(
    client: httpx.Client,
    email: str,
    first_name: str,
    last_name: str,
) -> str:
    """Register a user with custom names, activate the account, and return their token.

    :param client: httpx.Client instance
    :param email: User email address
    :param first_name: First name
    :param last_name: Last name
    :return: JWT access token string
    """
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            "first_name": first_name,
            "last_name": last_name,
        },
    ).raise_for_status()
    verify_user_email(email)

    response = client.post(
        "/auth/login",
        data={"username": email, "password": DEFAULT_PASSWORD},
    )
    response.raise_for_status()
    # Drop the session cookies the login set, so header-based tests authenticate purely
    # via the returned token and no ambient cookie overrides an explicit Authorization.
    client.cookies.clear()
    return response.json()["access_token"]


def create_project_with_scale(
    client: httpx.Client,
    token: str,
    name: str,
    scale_min: float,
    scale_max: float,
) -> dict:
    """Create a project with custom scale range.

    :param client: httpx.Client instance
    :param token: Admin user's access token
    :param name: Project name
    :param scale_min: Minimum scale value
    :param scale_max: Maximum scale value
    :return: Project response dict with 'id' field
    """
    response = client.post(
        "/projects",
        json={"name": name, "scale_min": scale_min, "scale_max": scale_max},
        headers=auth_headers(token),
    )
    response.raise_for_status()
    return response.json()


def submit_opinion(
    client: httpx.Client,
    token: str,
    project_id: str,
    lower_bound: float = 40.0,
    peak: float = 60.0,
    upper_bound: float = 80.0,
    position: str = "Expert",
) -> dict:
    """Submit an opinion and return response data.

    :param client: httpx.Client instance
    :param token: User's access token
    :param project_id: Project UUID string
    :param lower_bound: Fuzzy number lower bound
    :param peak: Fuzzy number peak value
    :param upper_bound: Fuzzy number upper bound
    :param position: Expert's position title
    :return: Opinion response dict
    """
    response = client.post(
        f"/projects/{project_id}/opinions",
        json={
            "position": position,
            "lower_bound": lower_bound,
            "peak": peak,
            "upper_bound": upper_bound,
        },
        headers=auth_headers(token),
    )
    response.raise_for_status()
    return response.json()
