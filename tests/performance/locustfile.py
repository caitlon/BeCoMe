"""Locust performance tests for BeCoMe API.

Tests the /api/v1/calculate endpoint with varying expert counts
to measure response time under load.

The route needs a signed-in user. Each simulated user logs in with the account in
``BECOME_LOAD_EMAIL`` and ``BECOME_LOAD_PASSWORD`` (a verified account that already
exists) and sends its token as a Bearer header. The limit of 60 requests a minute is
counted per account, so start the server with ``TESTING=1`` for a load run.

Usage::

    # Web UI (http://localhost:8089)
    uv run locust -f tests/performance/locustfile.py --host http://localhost:8000

    # Headless (60s run, 10 users)
    uv run locust -f tests/performance/locustfile.py \\
        --host http://localhost:8000 --headless \\
        --users 10 --spawn-rate 2 --run-time 60s --csv results
"""

import os

from locust import HttpUser, between, task


def _generate_experts(count: int) -> list[dict[str, object]]:
    """Generate expert opinion payload with given count."""
    return [
        {
            "name": f"Expert_{i}",
            "lower": float(i),
            "peak": float(i + 5),
            "upper": float(i + 10),
        }
        for i in range(count)
    ]


# Pre-generate payloads to avoid measuring generation time
PAYLOAD_10 = {"experts": _generate_experts(10)}
PAYLOAD_100 = {"experts": _generate_experts(100)}
PAYLOAD_1000 = {"experts": _generate_experts(1000)}


class CalculateUser(HttpUser):
    """Simulates users calling the /api/v1/calculate endpoint."""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        """Log in and keep the access token for every later request."""
        response = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": os.environ["BECOME_LOAD_EMAIL"],
                "password": os.environ["BECOME_LOAD_PASSWORD"],
            },
            name="/auth/login",
        )
        response.raise_for_status()
        # The login also set session cookies; drop them so the Bearer header is the only
        # credential and the CSRF guard stays out of the way.
        self.client.cookies.clear()
        self.client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"

    @task(5)
    def calculate_10_experts(self) -> None:
        """Calculate with 10 experts (typical use case)."""
        self.client.post(
            "/api/v1/calculate",
            json=PAYLOAD_10,
            name="/calculate [10 experts]",
        )

    @task(3)
    def calculate_100_experts(self) -> None:
        """Calculate with 100 experts (medium load)."""
        self.client.post(
            "/api/v1/calculate",
            json=PAYLOAD_100,
            name="/calculate [100 experts]",
        )

    @task(1)
    def calculate_1000_experts(self) -> None:
        """Calculate with 1000 experts (stress test)."""
        self.client.post(
            "/api/v1/calculate",
            json=PAYLOAD_1000,
            name="/calculate [1000 experts]",
        )

    @task(1)
    def health_check(self) -> None:
        """Check API health (baseline measurement)."""
        self.client.get("/api/v1/health", name="/health")
