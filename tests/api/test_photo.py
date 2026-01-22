"""Tests for photo upload/delete endpoints."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api.config import get_settings
from api.db.models import (  # noqa: F401
    CalculationResult,
    ExpertOpinion,
    Invitation,
    PasswordResetToken,
    Project,
    ProjectMember,
    User,
)
from api.db.session import get_session
from api.dependencies import get_storage_service
from api.middleware.exception_handlers import register_exception_handlers
from api.routes import auth, users
from api.services.storage.azure_blob_service import AzureBlobStorageService
from api.services.storage.exceptions import StorageDeleteError, StorageUploadError


def _create_test_app() -> FastAPI:
    """Create FastAPI app for testing."""
    settings = get_settings()
    app = FastAPI(
        title="BeCoMe API Test",
        version=settings.api_version,
    )
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(users.router)
    return app


def _register_and_login(client: TestClient) -> str:
    """Register a user and return access token."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "photo@example.com",
            "password": "SecurePass123",
            "first_name": "Photo",
            "last_name": "Test",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "photo@example.com", "password": "SecurePass123"},
    )
    return response.json()["access_token"]


# Valid JPEG magic bytes (minimal valid JPEG header)
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100

# Valid PNG magic bytes
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

# Invalid file (text pretending to be JPEG)
INVALID_FILE_BYTES = b"This is not an image file"


@pytest.fixture
def client_with_mock_storage():
    """Create test client with mocked storage service."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    test_app = _create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    mock_storage = MagicMock(spec=AzureBlobStorageService)
    mock_storage.upload_file.return_value = "https://storage.blob.core.windows.net/photos/test.jpg"

    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_storage_service] = lambda: mock_storage

    with TestClient(test_app) as test_client:
        yield test_client, mock_storage

    test_engine.dispose()


@pytest.fixture
def client_without_storage():
    """Create test client with storage service returning None."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    test_app = _create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_storage_service] = lambda: None

    with TestClient(test_app) as test_client:
        yield test_client

    test_engine.dispose()


class TestPhotoUpload:
    """Tests for POST /api/v1/users/me/photo."""

    def test_upload_photo_success(self, client_with_mock_storage):
        """Successful photo upload returns updated user with photo_url."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = _register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 200
        data = response.json()
        assert data["photo_url"] == "https://storage.blob.core.windows.net/photos/test.jpg"
        mock_storage.upload_file.assert_called_once()

    def test_upload_photo_invalid_content_type(self, client_with_mock_storage):
        """Upload with invalid content type returns 400."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = _register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("doc.pdf", b"PDF content", "application/pdf")},
        )

        # THEN
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_photo_content_mismatch(self, client_with_mock_storage):
        """Upload where content doesn't match claimed type returns 400."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = _register_and_login(client)

        # WHEN - claim JPEG but send text
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("fake.jpg", INVALID_FILE_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    def test_upload_photo_too_large(self, client_with_mock_storage):
        """Upload exceeding 5MB returns 400."""
        # GIVEN
        client, _ = client_with_mock_storage
        token = _register_and_login(client)
        large_file = VALID_JPEG_BYTES[:11] + b"\x00" * (6 * 1024 * 1024)  # >5MB

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("large.jpg", large_file, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 400
        assert "too large" in response.json()["detail"]

    def test_upload_photo_storage_unavailable(self, client_without_storage):
        """Upload when storage not configured returns 503."""
        # GIVEN
        client = client_without_storage
        token = _register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 503
        assert "not available" in response.json()["detail"]

    def test_upload_photo_storage_error(self, client_with_mock_storage):
        """Upload failure from storage returns 503."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        mock_storage.upload_file.side_effect = StorageUploadError("Azure error")
        token = _register_and_login(client)

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 503
        assert "Failed to upload" in response.json()["detail"]

    def test_upload_photo_replaces_old_photo(self, client_with_mock_storage):
        """Uploading new photo deletes old one."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = _register_and_login(client)

        # Upload first photo
        client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo1.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # WHEN - upload second photo
        mock_storage.upload_file.return_value = (
            "https://storage.blob.core.windows.net/photos/test2.jpg"
        )
        response = client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo2.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # THEN
        assert response.status_code == 200
        mock_storage.delete_file.assert_called_once()  # Old photo deleted

    def test_upload_photo_unauthorized(self, client_with_mock_storage):
        """Upload without auth token returns 401."""
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
        """Delete photo removes from storage and clears DB."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = _register_and_login(client)

        # Upload photo first
        client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # WHEN
        response = client.delete(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN
        assert response.status_code == 204
        mock_storage.delete_file.assert_called()

        # Verify photo_url is cleared
        profile = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile.json()["photo_url"] is None

    def test_delete_photo_no_photo(self, client_with_mock_storage):
        """Delete when no photo exists returns 204 (no-op)."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = _register_and_login(client)

        # WHEN
        response = client.delete(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN
        assert response.status_code == 204
        mock_storage.delete_file.assert_not_called()

    def test_delete_photo_storage_error_still_clears_db(self, client_with_mock_storage):
        """Delete continues even if storage deletion fails."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = _register_and_login(client)

        # Upload photo first
        client.post(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # Make delete_file raise error
        mock_storage.delete_file.side_effect = StorageDeleteError("Azure error")

        # WHEN
        response = client.delete(
            "/api/v1/users/me/photo",
            headers={"Authorization": f"Bearer {token}"},
        )

        # THEN - should still succeed
        assert response.status_code == 204

        # Verify photo_url is cleared in DB
        profile = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert profile.json()["photo_url"] is None

    def test_delete_photo_unauthorized(self, client_with_mock_storage):
        """Delete without auth token returns 401."""
        # GIVEN
        client, _ = client_with_mock_storage

        # WHEN
        response = client.delete("/api/v1/users/me/photo")

        # THEN
        assert response.status_code == 401


class TestMagicBytesValidation:
    """Tests for magic bytes validation."""

    def test_valid_jpeg(self):
        """Valid JPEG passes validation."""
        assert AzureBlobStorageService.validate_image_content(VALID_JPEG_BYTES, "image/jpeg")

    def test_valid_png(self):
        """Valid PNG passes validation."""
        assert AzureBlobStorageService.validate_image_content(VALID_PNG_BYTES, "image/png")

    def test_invalid_content(self):
        """Invalid content fails validation."""
        assert not AzureBlobStorageService.validate_image_content(INVALID_FILE_BYTES, "image/jpeg")

    def test_mismatched_type(self):
        """JPEG bytes with PNG claimed type fails."""
        assert not AzureBlobStorageService.validate_image_content(VALID_JPEG_BYTES, "image/png")

    def test_empty_content(self):
        """Empty content fails validation."""
        assert not AzureBlobStorageService.validate_image_content(b"", "image/jpeg")
