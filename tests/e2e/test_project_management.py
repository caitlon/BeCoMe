"""E2E tests for project management: update, standalone calculate, invitations."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.e2e.conftest import (
    auth_headers,
    create_project,
    create_project_with_scale,
    invite_and_accept,
    register_user,
    submit_opinion,
    unique_email,
)


@pytest.mark.e2e
class TestUpdateProject:
    """PATCH /projects/{id} must update project fields."""

    def test_update_project_name_and_description_persists(self, http_client):
        """Admin renames project and adds description."""
        # GIVEN — a project
        email = unique_email("projup")
        token = register_user(http_client, email)
        project = create_project(http_client, token, "Original Name")

        # WHEN — update name and description
        update_resp = http_client.patch(
            f"/projects/{project['id']}",
            json={"name": "Renamed Project", "description": "New description"},
            headers=auth_headers(token),
        )

        # THEN — response reflects changes
        assert update_resp.status_code == 200
        body = update_resp.json()
        assert body["name"] == "Renamed Project"
        assert body["description"] == "New description"

        # Verify via GET
        get_resp = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(token),
        )
        get_resp.raise_for_status()
        assert get_resp.json()["name"] == "Renamed Project"


@pytest.mark.e2e
class TestStandaloneCalculation:
    """POST /calculate must return correct BeCoMe results."""

    def test_standalone_calculate_three_experts_returns_correct_stats(self, http_client):
        """Three experts produce correct arithmetic mean, median, and best compromise."""
        # GIVEN — three expert opinions
        payload = {
            "experts": [
                {"name": "Expert A", "lower": 10.0, "peak": 20.0, "upper": 30.0},
                {"name": "Expert B", "lower": 20.0, "peak": 30.0, "upper": 40.0},
                {"name": "Expert C", "lower": 30.0, "peak": 40.0, "upper": 50.0},
            ]
        }

        # WHEN — call standalone calculate
        response = http_client.post("/calculate", json=payload)

        # THEN — correct results
        assert response.status_code == 200
        result = response.json()
        assert result["num_experts"] == 3

        # Arithmetic mean: (10+20+30)/3=20, (20+30+40)/3=30, (30+40+50)/3=40
        assert result["arithmetic_mean"]["lower"] == pytest.approx(20.0)
        assert result["arithmetic_mean"]["peak"] == pytest.approx(30.0)
        assert result["arithmetic_mean"]["upper"] == pytest.approx(40.0)

        # Median (odd, 3 experts sorted by centroid): middle expert is B=(20,30,40)
        assert result["median"]["lower"] == pytest.approx(20.0)
        assert result["median"]["peak"] == pytest.approx(30.0)
        assert result["median"]["upper"] == pytest.approx(40.0)

        # Best compromise = average of mean and median
        assert result["best_compromise"]["lower"] == pytest.approx(20.0)
        assert result["best_compromise"]["peak"] == pytest.approx(30.0)
        assert result["best_compromise"]["upper"] == pytest.approx(40.0)


@pytest.mark.e2e
class TestListPendingInvitations:
    """GET /projects/{id}/invitations must return pending invitations."""

    def test_list_pending_invitations_includes_invitee(self, http_client):
        """Invite an expert, verify the invitation appears in the list."""
        # GIVEN — a project owner and a registered expert
        owner_email = unique_email("invowner")
        expert_email = unique_email("invexpert")
        owner_token = register_user(http_client, owner_email)
        register_user(http_client, expert_email)
        project = create_project(http_client, owner_token, "Invitation List Test")

        # WHEN — owner invites expert
        invite_resp = http_client.post(
            f"/projects/{project['id']}/invite",
            json={"email": expert_email},
            headers=auth_headers(owner_token),
        )
        invite_resp.raise_for_status()

        # THEN — invitations list shows the pending invitation
        list_resp = http_client.get(
            f"/projects/{project['id']}/invitations",
            headers=auth_headers(owner_token),
        )
        assert list_resp.status_code == 200
        invitations = list_resp.json()
        assert len(invitations) >= 1
        emails = [inv["invitee_email"] for inv in invitations]
        assert expert_email in emails


@pytest.mark.e2e
class TestConcurrentOpinionSubmit:
    """Concurrent opinion submissions must not corrupt data."""

    def test_concurrent_submit_produces_one_opinion(self, http_client):
        """Two simultaneous POSTs → at least one succeeds, exactly one opinion stored."""
        # GIVEN — an invited expert
        owner_email = unique_email("concown")
        expert_email = unique_email("concexp")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token, "Concurrent Test")
        invite_and_accept(http_client, owner_token, expert_token, expert_email, project["id"])

        # WHEN — submit two opinions concurrently
        def post_opinion(values: tuple[float, float, float]) -> int:
            import httpx

            with httpx.Client(base_url=http_client.base_url, timeout=10) as c:
                resp = c.post(
                    f"/projects/{project['id']}/opinions",
                    json={
                        "position": "Expert",
                        "lower_bound": values[0],
                        "peak": values[1],
                        "upper_bound": values[2],
                    },
                    headers=auth_headers(expert_token),
                )
                return resp.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(post_opinion, (20.0, 40.0, 60.0))
            f2 = pool.submit(post_opinion, (30.0, 50.0, 70.0))
            results = [f1.result(), f2.result()]

        # THEN — at least one succeeds (the other may get 409 or 500 from
        # the DB unique constraint race), and exactly one opinion is stored
        assert 201 in results
        opinions_resp = http_client.get(
            f"/projects/{project['id']}/opinions",
            headers=auth_headers(expert_token),
        )
        opinions_resp.raise_for_status()
        expert_opinions = [o for o in opinions_resp.json() if o["user_email"] == expert_email]
        assert len(expert_opinions) == 1


@pytest.mark.e2e
class TestMultipleExperts:
    """Five experts must produce correct num_experts and arithmetic mean."""

    def test_five_experts_correct_calculation(self, http_client):
        """Five expert opinions → num_experts=5, arithmetic_mean matches."""
        # GIVEN — owner + 5 experts
        owner_email = unique_email("multiown")
        owner_token = register_user(http_client, owner_email)
        project = create_project(http_client, owner_token, "Multi Expert")

        expert_values = [
            (10.0, 30.0, 50.0),
            (20.0, 40.0, 60.0),
            (30.0, 50.0, 70.0),
            (40.0, 60.0, 80.0),
            (50.0, 70.0, 90.0),
        ]

        for i, (low, peak, up) in enumerate(expert_values):
            exp_email = unique_email(f"multi{i}")
            exp_token = register_user(http_client, exp_email)
            invite_and_accept(http_client, owner_token, exp_token, exp_email, project["id"])
            submit_opinion(
                http_client,
                exp_token,
                project["id"],
                lower_bound=low,
                peak=peak,
                upper_bound=up,
            )

        # WHEN — fetch result
        result_resp = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(owner_token),
        )
        result_resp.raise_for_status()
        result = result_resp.json()

        # THEN — 5 experts, arithmetic mean = (10+20+30+40+50)/5=30, etc.
        assert result["num_experts"] == 5
        assert result["arithmetic_mean"]["lower"] == pytest.approx(30.0)
        assert result["arithmetic_mean"]["peak"] == pytest.approx(50.0)
        assert result["arithmetic_mean"]["upper"] == pytest.approx(70.0)


@pytest.mark.e2e
class TestScaleBoundaryOpinion:
    """Opinion at exact scale boundaries must be accepted."""

    def test_opinion_at_exact_boundaries_returns_201(self, http_client):
        """lower=0, peak=50, upper=100 on default 0-100 scale → 201."""
        # GIVEN — a project with default scale
        email = unique_email("boundary")
        token = register_user(http_client, email)
        project = create_project(http_client, token)

        # WHEN — submit opinion at exact boundaries
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": 0.0,
                "peak": 50.0,
                "upper_bound": 100.0,
            },
            headers=auth_headers(token),
        )

        # THEN — accepted and persisted
        assert response.status_code == 201

        # Verify persisted values via GET
        opinions_resp = http_client.get(
            f"/projects/{project['id']}/opinions",
            headers=auth_headers(token),
        )
        opinions_resp.raise_for_status()
        opinions = opinions_resp.json()
        assert len(opinions) == 1
        assert opinions[0]["lower_bound"] == pytest.approx(0.0)
        assert opinions[0]["peak"] == pytest.approx(50.0)
        assert opinions[0]["upper_bound"] == pytest.approx(100.0)


@pytest.mark.e2e
class TestNegativeScaleProject:
    """Projects with negative scale ranges must work correctly."""

    def test_negative_scale_valid_opinion(self, http_client):
        """Scale -100..0, opinion (-80,-50,-20) → 201 with correct calculation."""
        # GIVEN — project with negative scale
        email = unique_email("negscale")
        token = register_user(http_client, email)
        project = create_project_with_scale(http_client, token, "Negative Scale", -100.0, 0.0)

        # WHEN — submit opinion within range
        response = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": -80.0,
                "peak": -50.0,
                "upper_bound": -20.0,
            },
            headers=auth_headers(token),
        )

        # THEN — accepted and calculation runs
        assert response.status_code == 201

        result_resp = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(token),
        )
        result_resp.raise_for_status()
        result = result_resp.json()
        assert result["num_experts"] == 1
        assert result["arithmetic_mean"]["lower"] == pytest.approx(-80.0)
        assert result["arithmetic_mean"]["peak"] == pytest.approx(-50.0)


@pytest.mark.e2e
class TestLikertInterpretation:
    """Likert interpretation depends on scale range."""

    def test_default_scale_returns_likert(self, http_client):
        """0-100 scale → likert_value int, likert_decision str."""
        # GIVEN — default scale (0-100) project with one opinion
        email = unique_email("likert")
        token = register_user(http_client, email)
        project = create_project(http_client, token)
        submit_opinion(http_client, token, project["id"])

        # WHEN — fetch result
        result_resp = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(token),
        )
        result_resp.raise_for_status()
        result = result_resp.json()

        # THEN — Likert fields populated
        assert isinstance(result["likert_value"], int)
        assert isinstance(result["likert_decision"], str)
        assert len(result["likert_decision"]) > 0

    def test_custom_scale_null_likert(self, http_client):
        """1-10 scale → likert_value is null."""
        # GIVEN — custom scale project
        email = unique_email("nolikert")
        token = register_user(http_client, email)
        project = create_project_with_scale(http_client, token, "Custom Scale", 1.0, 10.0)

        # Submit opinion within custom scale
        http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": 3.0,
                "peak": 5.0,
                "upper_bound": 8.0,
            },
            headers=auth_headers(token),
        ).raise_for_status()

        # WHEN — fetch result
        result_resp = http_client.get(
            f"/projects/{project['id']}/result",
            headers=auth_headers(token),
        )
        result_resp.raise_for_status()
        result = result_resp.json()

        # THEN — no Likert interpretation
        assert result["likert_value"] is None
        assert result["likert_decision"] is None


@pytest.mark.e2e
class TestProjectDeleteWhileExpertViews:
    """Deleted project must return 404 for expert."""

    def test_expert_404_after_delete(self, http_client):
        """Owner deletes project → expert GET → 404."""
        # GIVEN — owner + expert with opinion
        owner_email = unique_email("delown")
        expert_email = unique_email("delexp")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token, "Delete Test")
        invite_and_accept(http_client, owner_token, expert_token, expert_email, project["id"])
        submit_opinion(http_client, expert_token, project["id"])

        # WHEN — owner deletes project
        del_resp = http_client.delete(
            f"/projects/{project['id']}",
            headers=auth_headers(owner_token),
        )
        assert del_resp.status_code == 204

        # THEN — expert gets 404
        get_resp = http_client.get(
            f"/projects/{project['id']}",
            headers=auth_headers(expert_token),
        )
        assert get_resp.status_code == 404


@pytest.mark.e2e
class TestRemoveMemberThenSubmit:
    """Removed member must not be able to submit opinions."""

    def test_removed_member_cannot_submit(self, http_client):
        """Owner removes expert → expert POST opinion → 403 or 404."""
        # GIVEN — owner + expert in project
        owner_email = unique_email("rmown")
        expert_email = unique_email("rmexp")
        owner_token = register_user(http_client, owner_email)
        expert_token = register_user(http_client, expert_email)
        project = create_project(http_client, owner_token, "Remove Test")
        invite_and_accept(http_client, owner_token, expert_token, expert_email, project["id"])

        # Get expert user ID
        me_resp = http_client.get("/users/me", headers=auth_headers(expert_token))
        me_resp.raise_for_status()
        expert_id = me_resp.json()["id"]

        # WHEN — owner removes expert
        rm_resp = http_client.delete(
            f"/projects/{project['id']}/members/{expert_id}",
            headers=auth_headers(owner_token),
        )
        assert rm_resp.status_code == 204

        # THEN — expert cannot submit opinion
        opinion_resp = http_client.post(
            f"/projects/{project['id']}/opinions",
            json={
                "position": "Expert",
                "lower_bound": 20.0,
                "peak": 50.0,
                "upper_bound": 80.0,
            },
            headers=auth_headers(expert_token),
        )
        assert opinion_resp.status_code in (403, 404)
