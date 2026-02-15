"""E2E tests for photo upload (storage service unavailable)."""

import pytest

from tests.e2e.conftest import auth_headers, register_user, unique_email


@pytest.mark.e2e
class TestPhotoUploadWithoutStorage:
    """Photo upload without configured storage returns 503."""

    def test_upload_returns_503_without_storage(self, http_client):
        """POST /users/me/photo → 503 when Supabase storage is not configured."""
        # GIVEN — authenticated user
        email = unique_email("photo")
        token = register_user(http_client, email)

        # WHEN — attempt photo upload
        response = http_client.post(
            "/users/me/photo",
            files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")},
            headers=auth_headers(token),
        )

        # THEN — 503 with descriptive message
        assert response.status_code == 503
        assert "not available" in response.json()["detail"].lower()
