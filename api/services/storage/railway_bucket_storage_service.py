"""Railway Storage Bucket (S3-compatible) implementation of StorageService."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from api.services.storage.base import StorageService
from api.services.storage.exceptions import (
    StorageConfigurationError,
    StorageDeleteError,
    StorageError,
    StorageUploadError,
)
from api.services.storage.validation import extension_for

if TYPE_CHECKING:
    from api.config import Settings

logger = logging.getLogger("api.service.storage")

_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NoSuchBucket", "404", "NotFound"})


def _elapsed_ms(start: float) -> float:
    """Return milliseconds elapsed since ``start``, rounded to one decimal.

    :param start: ``perf_counter`` reading taken before the operation.
    :return: Elapsed time in milliseconds.
    """
    return round((perf_counter() - start) * 1000.0, 1)


class RailwayBucketStorageService(StorageService):
    """Store profile photos in a Railway Storage Bucket over the S3 API.

    Railway buckets are private, so files are served by the application rather
    than from a public bucket URL. Virtual-host addressing is used to match the
    Railway S3 gateway (``urlStyle: virtual-host``).

    :param settings: Application settings carrying the bucket credentials.
    :param client: Preconfigured S3 client; built from settings when omitted
        (injected directly in tests).
    :raises StorageConfigurationError: If the bucket settings are incomplete.
    """

    def __init__(self, settings: Settings, *, client: Any | None = None) -> None:
        """Validate configuration and build (or accept) an S3 client."""
        if not settings.storage_enabled or settings.bucket_name is None:
            raise StorageConfigurationError("Railway bucket credentials not configured")
        self._bucket: str = settings.bucket_name
        self._client: Any = client if client is not None else self._build_client(settings)

    @staticmethod
    def _build_client(settings: Settings) -> Any:
        """Create a path-style S3 client for the Railway bucket gateway.

        :param settings: Application settings with bucket credentials.
        :return: Configured boto3 S3 client.
        """
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            endpoint_url=settings.bucket_endpoint,
            aws_access_key_id=settings.bucket_access_key_id,
            aws_secret_access_key=settings.bucket_secret_access_key,
            region_name=settings.bucket_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    @staticmethod
    def build_key(user_id: str, content_type: str) -> str:
        """Build a unique object key namespaced by user.

        The extension comes from the validated content type, not the client
        filename, to prevent spoofing.

        :param user_id: Owner user id.
        :param content_type: Validated MIME type.
        :return: Key like ``profiles/<user_id>/<random>.<ext>``.
        """
        return f"profiles/{user_id}/{uuid4().hex[:12]}.{extension_for(content_type)}"

    def upload(self, content: bytes, content_type: str, user_id: str) -> str:
        """Store file bytes under a generated key.

        :param content: Raw file bytes (already validated).
        :param content_type: Validated MIME type.
        :param user_id: Owner user id.
        :return: Object key under which the file was stored.
        :raises StorageUploadError: If the upload fails.
        """
        key = self.build_key(user_id, content_type)
        start = perf_counter()
        try:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=content, ContentType=content_type
            )
        except Exception as exc:
            logger.error(
                "S3 upload failed",
                exc_info=exc,
                extra={
                    "event": "s3_upload_failed",
                    "user_id": user_id,
                    "key": key,
                    "duration_ms": _elapsed_ms(start),
                },
            )
            raise StorageUploadError(f"Failed to upload file: {exc}") from exc
        logger.info(
            "S3 upload",
            extra={
                "event": "s3_upload",
                "user_id": user_id,
                "key": key,
                "size_bytes": len(content),
                "duration_ms": _elapsed_ms(start),
            },
        )
        return key

    def open(self, key: str) -> tuple[bytes, str] | None:
        """Fetch a stored object by key.

        :param key: Object key.
        :return: ``(bytes, content_type)`` or None when the object is absent.
        :raises StorageError: If the fetch fails for a reason other than absence.
        """
        start = perf_counter()
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if self._is_not_found(exc):
                logger.info(
                    "S3 object missing",
                    extra={
                        "event": "s3_open_miss",
                        "key": key,
                        "duration_ms": _elapsed_ms(start),
                    },
                )
                return None
            logger.error(
                "S3 read failed",
                exc_info=exc,
                extra={
                    "event": "s3_open_failed",
                    "key": key,
                    "duration_ms": _elapsed_ms(start),
                },
            )
            raise StorageError(f"Failed to read file: {exc}") from exc
        body: bytes = response["Body"].read()
        content_type: str = response.get("ContentType") or "application/octet-stream"
        logger.info(
            "S3 open",
            extra={
                "event": "s3_open",
                "key": key,
                "size_bytes": len(body),
                "duration_ms": _elapsed_ms(start),
            },
        )
        return body, content_type

    def delete(self, key: str) -> bool:
        """Delete a stored object by key.

        :param key: Object key.
        :return: True when the delete request was issued.
        :raises StorageDeleteError: If deletion fails.
        """
        start = perf_counter()
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            logger.error(
                "S3 delete failed",
                exc_info=exc,
                extra={
                    "event": "s3_delete_failed",
                    "key": key,
                    "duration_ms": _elapsed_ms(start),
                },
            )
            raise StorageDeleteError(f"Failed to delete file: {exc}") from exc
        logger.info(
            "S3 delete",
            extra={"event": "s3_delete", "key": key, "duration_ms": _elapsed_ms(start)},
        )
        return True

    @staticmethod
    def _is_not_found(exc: Exception) -> bool:
        """Report whether an S3 error means the object is absent.

        :param exc: Exception raised by the S3 client.
        :return: True for a missing-object / missing-bucket error.
        """
        from botocore.exceptions import ClientError

        if isinstance(exc, ClientError):
            code = str(exc.response.get("Error", {}).get("Code", ""))
            return code in _NOT_FOUND_CODES
        return False
