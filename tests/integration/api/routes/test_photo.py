"""Tests for photo upload, delete, and proxy endpoints."""

import uuid
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from api.db.session import get_session
from api.dependencies import get_storage_service
from api.services.storage.base import StorageService
from api.services.storage.exceptions import (
    StorageDeleteError,
    StorageError,
    StorageUploadError,
)
from api.services.storage.stored_object import DEFAULT_CHUNK_SIZE, StoredObject
from tests.integration.api.conftest import auth_header, create_test_app, register_and_login


def _image_bytes(width: int = 8, height: int = 8, image_format: str = "JPEG") -> bytes:
    """Encode a real image, so uploads face the same decoder the endpoint uses.

    Hand-written magic bytes were enough while only the signature was checked, but the
    dimension guard actually parses the header -- a fake would be rejected as corrupt
    and the test would pass for the wrong reason.
    """
    buffer = BytesIO()
    mode = "L" if image_format == "PNG" else "RGB"
    Image.new(mode, (width, height), 120).save(buffer, format=image_format)
    return buffer.getvalue()


VALID_JPEG_BYTES = _image_bytes()

# Invalid file (text pretending to be JPEG)
INVALID_FILE_BYTES = b"This is not an image file"

# Object key the mocked storage returns for an upload.
UPLOADED_KEY = "profiles/test/deadbeef0001.jpg"

# A versioned photo URL always maps to the same bytes, so it is cacheable forever.
IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"

# The bare path has no version, so its bytes change with the photo and it gets a short TTL.
SHORT_CACHE_CONTROL = "public, max-age=300"


def _photo_stream(data: bytes = VALID_JPEG_BYTES) -> MagicMock:
    """Wrap a photo body in a mock, so its read and close calls are observable."""
    return MagicMock(wraps=BytesIO(data))


def _stored_photo(
    stream: MagicMock | None = None, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> StoredObject:
    """Build an open handle over an in-memory photo body.

    ``open`` hands back a single-use handle, so every call needs a fresh one --
    a shared instance would arrive already closed on the second request.
    """
    return StoredObject(
        stream if stream is not None else _photo_stream(),
        "image/jpeg",
        len(VALID_JPEG_BYTES),
        chunk_size=chunk_size,
    )


@pytest.fixture
def client_with_mock_storage(test_engine):
    """Create a test client with a mocked storage service."""
    test_app = create_test_app()

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    mock_storage = MagicMock(spec=StorageService)
    mock_storage.upload.return_value = UPLOADED_KEY
    mock_storage.open.side_effect = lambda _key: _stored_photo()

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

    def test_upload_rejects_a_decompression_bomb(self, client_with_mock_storage):
        """A small file declaring a huge canvas is rejected before it reaches storage.

        The 5 MB byte cap passes this file easily -- the danger is the 25-megapixel
        canvas it declares, which costs hundreds of megabytes the moment it decodes.
        """
        # GIVEN a 5000x5000 PNG that weighs well under the size limit
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "bomb@example.com")
        bomb = _image_bytes(5000, 5000, "PNG")
        assert len(bomb) < 5 * 1024 * 1024

        # WHEN
        response = client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("huge.png", bomb, "image/png")},
        )

        # THEN
        assert response.status_code == 400
        assert "dimensions" in response.json()["detail"].lower()
        mock_storage.upload.assert_not_called()

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

    @staticmethod
    def _user_with_photo(client, email: str) -> str:
        """Register a user, upload a photo, and return the user id."""
        token = register_and_login(client, email)
        user_id = client.get("/api/v1/users/me", headers=auth_header(token)).json()["id"]
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )
        return str(user_id)

    def test_streams_photo_bytes(self, client_with_mock_storage):
        """The proxy streams the stored object with its content type and size."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        user_id = self._user_with_photo(client, "proxy@example.com")

        # WHEN - public endpoint, no auth header
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/jpeg")
        assert response.headers["content-length"] == str(len(VALID_JPEG_BYTES))
        assert response.content == VALID_JPEG_BYTES
        mock_storage.open.assert_called_with(UPLOADED_KEY)

    def test_pulls_the_body_in_chunks_instead_of_buffering_it(self, client_with_mock_storage):
        """The route hands the open stream to the response, chunk by chunk.

        With a chunk size below the payload, a buffering route would show a single
        read; a streaming one shows one read per chunk plus the closing empty read.
        """
        # GIVEN a handle that yields the photo four bytes at a time
        client, mock_storage = client_with_mock_storage
        user_id = self._user_with_photo(client, "chunked@example.com")
        stream = _photo_stream()
        mock_storage.open.side_effect = None
        mock_storage.open.return_value = _stored_photo(stream, chunk_size=4)

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN one read per chunk, plus the empty read that ends the stream
        assert response.content == VALID_JPEG_BYTES
        expected_reads = -(-len(VALID_JPEG_BYTES) // 4) + 1
        assert stream.read.call_count == expected_reads

    def test_sets_an_immutable_year_long_cache_header(self, client_with_mock_storage):
        """A versioned photo URL is cacheable indefinitely."""
        # GIVEN
        client, _ = client_with_mock_storage
        user_id = self._user_with_photo(client, "cached@example.com")

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo?v=deadbeef0001")

        # THEN
        assert response.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL

    def test_an_unversioned_url_is_not_pinned_for_a_year(self, client_with_mock_storage):
        """
        GIVEN a photo requested through the bare path, with no version parameter
        WHEN the response is served
        THEN it carries the short cache header instead of the immutable one

        The bare path is a stable URL whose bytes change when the photo does. Nothing
        the API emits looks like that, but pinning it in a shared cache would serve one
        person's replaced avatar to everyone who asked for a year.
        """
        # GIVEN
        client, _ = client_with_mock_storage
        user_id = self._user_with_photo(client, "unversioned@example.com")

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.headers["cache-control"] == SHORT_CACHE_CONTROL
        assert response.headers["cache-control"] != IMMUTABLE_CACHE_CONTROL

    def test_closes_the_stream_once_the_response_is_written(self, client_with_mock_storage):
        """The bucket connection is released, not left in the pool."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        user_id = self._user_with_photo(client, "closed@example.com")
        stream = _photo_stream()
        stored = _stored_photo(stream)
        mock_storage.open.side_effect = None
        mock_storage.open.return_value = stored

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN the handle is released once, though two paths try to release it
        assert response.status_code == 200
        assert stored.closed is True
        stream.close.assert_called_once()

    def test_returns_404_when_the_user_does_not_exist(self, client_with_mock_storage):
        """An unknown user id returns 404 without reaching storage."""
        # GIVEN
        client, mock_storage = client_with_mock_storage

        # WHEN
        response = client.get(f"/api/v1/users/{uuid.uuid4()}/photo")

        # THEN
        assert response.status_code == 404
        mock_storage.open.assert_not_called()

    def test_returns_404_when_user_has_no_photo(self, client_with_mock_storage):
        """The proxy returns 404 when the user has no photo set."""
        # GIVEN
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "nophoto@example.com")
        user_id = client.get("/api/v1/users/me", headers=auth_header(token)).json()["id"]

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.status_code == 404
        mock_storage.open.assert_not_called()

    def test_returns_404_when_storage_unavailable(self, client_without_storage):
        """The proxy returns 404 when storage is not configured."""
        # GIVEN
        client = client_without_storage

        # WHEN
        response = client.get(f"/api/v1/users/{uuid.uuid4()}/photo")

        # THEN
        assert response.status_code == 404

    def test_returns_404_when_stored_object_missing(self, client_with_mock_storage):
        """The proxy returns 404 when the key is set but the object is gone from storage."""
        # GIVEN - a user with a photo whose backing object has since disappeared
        client, mock_storage = client_with_mock_storage
        user_id = self._user_with_photo(client, "gone@example.com")
        mock_storage.open.side_effect = None
        mock_storage.open.return_value = None

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.status_code == 404

    def test_storage_fault_does_not_leak_the_bucket_details(self, client_with_mock_storage):
        """A storage read fault answers 404 without echoing the underlying error.

        This endpoint is public (image tags cannot send auth headers), and the wrapped
        botocore message carries the bucket host and object key.
        """
        # GIVEN - a user with a photo, and storage that fails on read
        client, mock_storage = client_with_mock_storage
        user_id = self._user_with_photo(client, "fault@example.com")
        mock_storage.open.side_effect = StorageError(
            "Failed to read file: Could not connect to the endpoint URL: "
            f"https://private-bucket.example/{UPLOADED_KEY}"
        )

        # WHEN
        response = client.get(f"/api/v1/users/{user_id}/photo")

        # THEN
        assert response.status_code == 404
        assert response.json() == {"detail": "Photo not found"}
        assert "private-bucket" not in response.text


class TestAccountDeletionRemovesPhoto:
    """Deleting an account must also remove its photo blob (GDPR Art. 17)."""

    def test_delete_account_removes_photo_from_storage(self, client_with_mock_storage):
        """Deleting the account deletes the user's photo object from storage."""
        # GIVEN a user with an uploaded photo
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "erase@example.com")
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )

        # WHEN the account is deleted
        response = client.delete("/api/v1/users/me", headers=auth_header(token))

        # THEN the photo object is removed from storage
        assert response.status_code == 204
        mock_storage.delete.assert_called_once_with(UPLOADED_KEY)

    def test_delete_account_without_photo_skips_storage(self, client_with_mock_storage):
        """Deleting an account that has no photo never calls storage."""
        # GIVEN a user with no uploaded photo
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "nophoto-erase@example.com")

        # WHEN the account is deleted
        response = client.delete("/api/v1/users/me", headers=auth_header(token))

        # THEN storage is never asked to delete anything
        assert response.status_code == 204
        mock_storage.delete.assert_not_called()

    def test_delete_account_succeeds_when_storage_delete_fails(self, client_with_mock_storage):
        """Account deletion completes even when the photo blob removal fails."""
        # GIVEN a user with a photo whose storage removal will error
        client, mock_storage = client_with_mock_storage
        token = register_and_login(client, "brokenstorage@example.com")
        client.post(
            "/api/v1/users/me/photo",
            headers=auth_header(token),
            files={"file": ("photo.jpg", VALID_JPEG_BYTES, "image/jpeg")},
        )
        mock_storage.delete.side_effect = StorageDeleteError("bucket error")

        # WHEN the account is deleted
        response = client.delete("/api/v1/users/me", headers=auth_header(token))

        # THEN the account is still removed (the storage failure is suppressed)
        assert response.status_code == 204
        mock_storage.delete.assert_called_once_with(UPLOADED_KEY)
        profile = client.get("/api/v1/users/me", headers=auth_header(token))
        assert profile.status_code == 401
