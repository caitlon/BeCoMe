"""Create the accounts and data the DAST scanners work with.

Run from the repository root with the project's own environment, against the API the job
started and the database it uses::

    PYTHONPATH=. uv run python .github/dast/fixtures.py dast-out

Two users are registered, A and B, with passwords made up for this run alone. Their
addresses are verified straight through the database (registration mails the activation
link and nothing here can read the mail), each user logs in and creates a project, and A
adds one opinion. The script writes two files into the output directory:

- ``fixtures.json``: the ids the ZAP spec step binds into its paths (no passwords).
- ``auth.json``: a Web Fuzzing Commons file that lets Schemathesis log both users in. It
  holds the passwords, so it stays out of the reports pushed anywhere.

The only output on stdout is one status line.
"""

import json
import secrets
import sys
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.engine import make_url
from sqlmodel import Session, select

from api.config import get_settings
from api.db.engine import get_engine
from api.db.models import User
from api.db.utils import utc_now

BASE_URL = "http://127.0.0.1:8000/api/v1"
USERS = {"A": "dast-a@e2e-test.com", "B": "dast-b@e2e-test.com"}
TIMEOUT_SECONDS = 15
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1"})


def require_local_database() -> None:
    """Stop the script unless the configured database is on this machine.

    The script verifies accounts straight in the database, so a local run with a real
    ``.env`` must never reach another one. The URL is not printed, it holds a password. A
    ``host``, ``hostaddr`` or ``service`` entry in the query string can override the URL's
    host in libpq, so any of them also counts as not local.
    """
    url = make_url(get_settings().database_url)
    if url.host not in LOCAL_DATABASE_HOSTS or {"host", "hostaddr", "service"} & set(url.query):
        sys.exit("fixtures: refusing to run, DATABASE_URL does not point at localhost")


def make_password() -> str:
    """Make a password that meets the registration policy and is unique to this run.

    :return: 24 random hex characters and the suffix ``-Aa1``, which supplies an upper-case
        letter, a lower-case letter, a digit and a symbol, 28 characters in all
    """
    return f"{secrets.token_hex(12)}-Aa1"


def verify_email(email: str) -> None:
    """Mark a registered address as verified in the database.

    :param email: Address of an account the API has just registered
    :raises RuntimeError: When no account exists for the address
    """
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None:
            raise RuntimeError("a fixture account was not registered")
        user.email_verified_at = utc_now()
        session.add(user)
        session.commit()


def register_and_login(client: httpx.Client, label: str, password: str) -> dict[str, str]:
    """Register one fixture user, verify the address, log in and read the user id.

    :param client: Client with the API's base URL
    :param label: ``A`` or ``B``
    :param password: Password for the new account
    :return: The user id and the Bearer header value of the new session
    """
    email = USERS[label]
    response = client.post(
        "/auth/register",
        json={"email": email, "password": password, "first_name": label, "last_name": "Dast"},
    )
    response.raise_for_status()
    verify_email(email)
    response = client.post("/auth/login", data={"username": email, "password": password})
    response.raise_for_status()
    # The login also sets session cookies; the scanners use the Bearer header only.
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    response = client.get("/users/me", headers=headers)
    response.raise_for_status()
    return {"user_id": response.json()["id"], "authorization": headers["Authorization"]}


def create_project(client: httpx.Client, label: str, authorization: str) -> str:
    """Create a project owned by a fixture user.

    :param client: Client with the API's base URL
    :param label: ``A`` or ``B``
    :param authorization: Bearer header value of the owner
    :return: The id of the new project
    """
    response = client.post(
        "/projects",
        json={"name": f"DAST project {label}", "scale_min": 0, "scale_max": 100, "scale_unit": "%"},
        headers={"Authorization": authorization},
    )
    response.raise_for_status()
    return str(response.json()["id"])


def build_auth_file(password: str) -> dict[str, Any]:
    """Describe the two logins in the Web Fuzzing Commons format Schemathesis reads.

    :param password: Password shared by both fixture accounts
    :return: The auth file content, one entry per fixture user
    """
    entries = [
        {
            "name": f"user{label}",
            "loginEndpointAuth": {
                "verb": "POST",
                "endpoint": "/api/v1/auth/login",
                "contentType": "application/x-www-form-urlencoded",
                "payloadUserPwd": {
                    "username": email,
                    "password": password,
                    "usernameField": "username",
                    "passwordField": "password",  # pragma: allowlist secret
                },
                "token": {
                    "extractFrom": "body",
                    "extractSelector": "/access_token",
                    "sendIn": "header",
                    "sendName": "Authorization",
                    "sendTemplate": "Bearer {token}",
                },
            },
        }
        for label, email in USERS.items()
    ]
    return {"auth": entries}


def main(out_dir: Path) -> None:
    """Create the fixtures and write ``fixtures.json`` and ``auth.json``.

    :param out_dir: Directory that receives both files
    """
    require_local_database()
    password = make_password()
    fixtures: dict[str, dict[str, str]] = {}
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_SECONDS) as client:
        for label in USERS:
            session = register_and_login(client, label, password)
            project_id = create_project(client, label, session["authorization"])
            fixtures[label] = {"user_id": session["user_id"], "project_id": project_id}
            if label == "A":
                response = client.post(
                    f"/projects/{project_id}/opinions",
                    json={"position": "Analyst", "lower_bound": 10, "peak": 20, "upper_bound": 30},
                    headers={"Authorization": session["authorization"]},
                )
                response.raise_for_status()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fixtures.json").write_text(json.dumps({"users": fixtures}, indent=1))
    (out_dir / "auth.json").write_text(json.dumps(build_auth_file(password), indent=1))
    print("fixtures: 2 users, 2 projects, 1 opinion")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "dast-out"))
