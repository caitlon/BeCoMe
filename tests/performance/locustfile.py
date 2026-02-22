"""Locust performance tests for BeCoMe API.

Tests the /api/v1/calculate endpoint with varying expert counts
to measure response time under load for thesis benchmarks.

Usage::

    # Web UI (http://localhost:8089)
    uv run locust -f tests/performance/locustfile.py --host http://localhost:8000

    # Headless (60s run, 10 users)
    uv run locust -f tests/performance/locustfile.py \\
        --host http://localhost:8000 --headless \\
        --users 10 --spawn-rate 2 --run-time 60s --csv results
"""

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
