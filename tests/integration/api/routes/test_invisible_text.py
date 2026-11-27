"""Integration test: stored user text carries no characters that render as nothing."""

from tests.integration.api.conftest import auth_header, register_and_login

# A bidirectional override, a zero-width space and a soft hyphen.
_INVISIBLE = "\u202e\u200b\u00ad"


class TestInvisibleCharactersInStoredText:
    """Project and opinion text is cleaned on the way in."""

    def test_project_and_opinion_text_is_stored_without_them(self, client):
        """
        GIVEN a project and an opinion whose text holds invisible characters
        WHEN they are created through the API and read back
        THEN the stored text has none of them, and the line break and tab are kept
        """
        # GIVEN
        token = register_and_login(client)
        headers = auth_header(token)

        # WHEN
        created = client.post(
            "/api/v1/projects",
            json={
                "name": f"Pro{_INVISIBLE}ject",
                "description": f"one{_INVISIBLE}\n\ttwo",
                "scale_unit": f"%{_INVISIBLE}",
            },
            headers=headers,
        )
        project_id = created.json()["id"]
        opinion = client.post(
            f"/api/v1/projects/{project_id}/opinions",
            json={
                "position": f"Ana{_INVISIBLE}lyst",
                "lower_bound": 10.0,
                "peak": 20.0,
                "upper_bound": 30.0,
            },
            headers=headers,
        )
        project = client.get(f"/api/v1/projects/{project_id}", headers=headers).json()
        opinions = client.get(f"/api/v1/projects/{project_id}/opinions", headers=headers).json()

        # THEN
        assert created.status_code == 201
        assert opinion.status_code == 201
        assert project["name"] == "Project"
        assert project["description"] == "one\n\ttwo"
        assert project["scale_unit"] == "%"
        assert [item["position"] for item in opinions] == ["Analyst"]
