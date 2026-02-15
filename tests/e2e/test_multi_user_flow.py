"""E2E tests for multi-expert collaboration and result aggregation."""

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    invite_and_accept,
    register_user,
    submit_opinion,
    unique_email,
)


@pytest.mark.e2e
class TestTwoExpertsCollaboration:
    """Two experts submit opinions and see aggregated results."""

    def test_two_experts_contribute_and_see_aggregated_result(self, http_client):
        """Both opinions are reflected in the calculation result."""
        # GIVEN — owner and expert registered
        owner_email = unique_email("owner")
        expert_email = unique_email("expert")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)

        # Owner creates project and invites expert
        project = create_project(http_client, owner_token, "Two Experts E2E")
        invite_and_accept(http_client, owner_token, expert_token, expert_email, project["id"])

        # WHEN — both submit opinions
        submit_opinion(
            http_client,
            owner_token,
            project["id"],
            lower_bound=20.0,
            peak=50.0,
            upper_bound=80.0,
            position="Owner",
        )
        submit_opinion(
            http_client,
            expert_token,
            project["id"],
            lower_bound=30.0,
            peak=60.0,
            upper_bound=90.0,
            position="Expert",
        )

        # THEN — result aggregates both opinions
        result = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(owner_token),
        ).json()

        assert result is not None
        assert result["num_experts"] == 2

        # Arithmetic mean: ((20+30)/2, (50+60)/2, (80+90)/2) = (25, 55, 85)
        mean = result["arithmetic_mean"]
        assert abs(mean["lower"] - 25.0) < 0.01
        assert abs(mean["peak"] - 55.0) < 0.01
        assert abs(mean["upper"] - 85.0) < 0.01


@pytest.mark.e2e
class TestThreeExpertsMedian:
    """Three experts produce a meaningful median calculation."""

    def test_three_experts_odd_median(self, http_client):
        """With three opinions, median is the middle centroid."""
        # GIVEN — three users
        owner_email = unique_email("owner")
        expert1_email = unique_email("expert1")
        expert2_email = unique_email("expert2")
        owner_token = register_user(http_client, owner_email)
        expert1_token = register_user(http_client, expert1_email)
        expert2_token = register_user(http_client, expert2_email)

        project = create_project(http_client, owner_token, "Three Experts E2E")
        invite_and_accept(http_client, owner_token, expert1_token, expert1_email, project["id"])
        invite_and_accept(http_client, owner_token, expert2_token, expert2_email, project["id"])

        # WHEN — three different opinions
        # Centroids: (10+30+50)/3=30, (20+40+60)/3=40, (40+60+80)/3=60
        submit_opinion(
            http_client,
            owner_token,
            project["id"],
            lower_bound=10.0,
            peak=30.0,
            upper_bound=50.0,
            position="Owner",
        )
        submit_opinion(
            http_client,
            expert1_token,
            project["id"],
            lower_bound=20.0,
            peak=40.0,
            upper_bound=60.0,
            position="Expert 1",
        )
        submit_opinion(
            http_client,
            expert2_token,
            project["id"],
            lower_bound=40.0,
            peak=60.0,
            upper_bound=80.0,
            position="Expert 2",
        )

        # THEN — result has 3 experts
        result = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(owner_token),
        ).json()

        assert result is not None
        assert result["num_experts"] == 3

        # Median (odd count) should be the middle opinion sorted by centroid
        # Centroids: 30, 40, 60 → median is the opinion with centroid 40: (20, 40, 60)
        median = result["median"]
        assert abs(median["lower"] - 20.0) < 0.01
        assert abs(median["peak"] - 40.0) < 0.01
        assert abs(median["upper"] - 60.0) < 0.01
