"""E2E test fixtures — real server, real database."""

import time
from uuid import uuid4

import httpx
import pytest

E2E_BASE_URL = "http://localhost:8000/api/v1"
DEFAULT_PASSWORD = "SecurePass123!"


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
        except httpx.ConnectError:
            pass
        if attempt < 9:
            time.sleep(1)
    pytest.skip("API server not running at localhost:8000")


@pytest.fixture
def http_client(api_url):
    """Create httpx client scoped to a single test.

    :param api_url: Base API URL from session fixture
    :return: httpx.Client instance
    """
    with httpx.Client(base_url=api_url, timeout=10) as client:
        yield client


def unique_email(prefix: str = "user") -> str:
    """Generate a unique email address for test isolation.

    :param prefix: Email prefix (e.g., "owner", "expert")
    :return: Unique email string
    """
    return f"{prefix}-{uuid4().hex[:12]}@e2e-test.com"


def register_user(client: httpx.Client, email: str) -> str:
    """Register a new user and return their access token.

    :param client: httpx.Client instance
    :param email: User email address
    :return: JWT access token string
    """
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            "first_name": "Test",
            "last_name": "User",
        },
    )
    response = client.post(
        "/auth/login",
        data={"username": email, "password": DEFAULT_PASSWORD},
    )
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
    client.post(
        f"/projects/{project_id}/invite",
        json={"email": expert_email},
        headers=auth_headers(owner_token),
    )

    invitations = client.get("/invitations", headers=auth_headers(expert_token)).json()
    invitation_id = invitations[0]["id"]

    client.post(
        f"/invitations/{invitation_id}/accept",
        headers=auth_headers(expert_token),
    )


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
    return response.json()
