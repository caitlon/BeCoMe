"""Tests for photo upload, delete, and proxy endpoints."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies import get_storage_service
from api.services.storage.base import StorageService
from api.services.storage.exceptions import StorageDeleteError, StorageUploadError
from tests.integration.api.conftest import auth_header, create_test_app, register_and_login

# Valid JPEG magic bytes (minimal valid JPEG header)
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100

# Invalid file (text pretending to be JPEG)
INVALID_FILE_BYTES = b"This is not an image file"

# Object key the mocked storage returns for an upload.
UPLOADED_KEY = "profiles/test/deadbeef0001.jpg"


@pytest.fixture
def client_with_mock_storage(test_engine):
    """Create a test client with a mocked storage service."""
    test_app = create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    mock_storage = MagicMock(spec=StorageService)
    mock_storage.upload.return_value = UPLOADED_KEY
    mock_storage.open.return_value = (VALID_JPEG_BYTES, "image/jpeg")

    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_storage_service] = lambda: mock_storage

    with TestClient(test_app) as test_client:
        try:
            yield test_client, mock_storage
        finally:
            test_app.dependency_overrides.clear()


@pytest.fixture
def client_without_storage(test_engine):
    """Create a test client with the storage service disabled (None)."""
    test_app = create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_storage_service] = lambda: None

    with TestClient(test_app) as test_client:
        try:
            yield test_client
        finally:
            test_app.dependency_overrides.clear()


class TestPhotoUpload:
    """Tests for POST /api/v1/users/me/photo."""

    def test_upload_photo_success(self, client_with_mock_storage):
        """Successful upload returns the user with a photo proxy URL."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 200
        url = response.json()["photo_url"]
        assert "/api/v1/users/" in url
        assert url.endswith("/photo?v=deadbeef0001")
        mock_storage.upload.assert_called_once()

    def test_upload_photo_invalid_content_type(self, client_with_mock_storage):
        """Upload with an invalid content type returns 400."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("doc.pdf", b"PDF content", "application/pdf")},
        )

        # THEN
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_photo_content_mismatch(self, client_with_mock_storage):
        """Upload where content does not match the claimed type returns 400."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")

        # WHEN - claim JPEG but send text
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("fake.jpg", INVALID_FILE_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    def test_upload_photo_too_large(self, client_with_mock_storage):
        """Upload exceeding 5MB returns 400."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")
        large_file = VALID_JPEG_BYTES[:11] + b"\x00" * (6 * 1024 * 1024)  # >5MB

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("large.jpg", large_file, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 400
        assert "too large" in response.json()["detail"]

    def test_upload_photo_storage_unavailable(self, client_without_storage):
        """Upload when storage is not configured returns 503."""
        # GIVEN
        client = client_without_storage
        token = register_and_login(client, "photo@example.com")

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]

    def test_upload_photo_storage_error(self, client_with_mock_storage):
        """An upload failure from storage returns 503."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        mock_storage.upload.side_effect = StorageUploadError("bucket error")
        token = register_and_login(client, "photo@example.com")

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 503
        assert "Failed to upload" in response.json()["detail"]

    def test_upload_photo_replaces_old_photo(self, client_with_mock_storage):
        """Uploading a new photo deletes the previous object."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")

        # Upload first photo
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo1.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # WHEN - upload a second photo
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo2.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 200
        mock_storage.delete.assert_called_once()  # Old object deleted

    def test_upload_photo_unauthorized(self, client_with_mock_storage):
        """Upload without an auth token returns 401."""
        # GIVEN
        client, _ = client_with_mock_storage

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 401


class TestPhotoDelete:
    """Tests for DELETE /api/v1/users/me/photo."""

    def test_delete_photo_success(self, client_with_mock_storage):
        """Deleting a photo removes it from storage and clears the DB."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # WHEN
        response = client.delete("/api/v1/users/me/photo", headers=auth_header(token))

        # THEN
        assert response.status_code == 204
        mock_storage.delete.assert_called()
        profile = client.get("/api/v1/users/me", headers=auth_header(token))
        assert profile.json()["photo_url"] is None

    def test_delete_photo_no_photo(self, client_with_mock_storage):
        """Deleting when no photo exists is a no-op returning 204."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")

        # WHEN
        response = client.delete("/api/v1/users/me/photo", headers=auth_header(token))

        # THEN
        assert response.status_code == 204
        mock_storage.delete.assert_not_called()

    def test_delete_photo_storage_error_still_clears_db(self, client_with_mock_storage):
        """Deletion continues even when storage removal fails."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "photo@example.com")
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )
        mock_storage.delete.side_effect = StorageDeleteError("bucket error")

        # WHEN
        response = client.delete("/api/v1/users/me/photo", headers=auth_header(token))

        # THEN
        assert response.status_code == 204
        profile = client.get("/api/v1/users/me", headers=auth_header(token))
        assert profile.json()["photo_url"] is None

    def test_delete_photo_unauthorized(self, client_with_mock_storage):
        """Delete without an auth token returns 401."""
        # GIVEN
        client, _ = client_with_mock_storage

        # WHEN
        response = client.delete("/api/v1/users/me/photo")

        # THEN
        assert response.status_code == 401


class TestPhotoProxy:
    """Tests for GET /api/v1/users/{user_id}/photo."""

    def test_streams_photo_bytes(self, client_with_mock_storage):
        """The proxy streams the stored object with its content type."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "proxy@example.com")
        user_id = client.get("/api/v1/users/me", headers=auth_header(token)).json()["id"]
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # WHEN - public endpoint, no auth header
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/jpeg")
        assert response.content == VALID_JPEG_BYTES
        mock_storage.open.assert_called_with(UPLOADED_KEY)

    def test_returns_404_when_user_has_no_photo(self, client_with_mock_storage):
        """The proxy returns 404 when the user has no photo set."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = register_and_login(client, "nophoto@example.com")
        user_id = client.get("/api/v1/users/me", headers=auth_header(token)).json()["id"]

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.status_code == 404

    def test_returns_404_when_storage_unavailable(self, client_without_storage):
        """The proxy returns 404 when storage is not configured."""
        # GIVEN
        client = client_without_storage

        # WHEN
        response = client.get(f"/api/v1/users/{uuid.uuid4()}/photo")

        # THEN
        assert response.status_code == 404
