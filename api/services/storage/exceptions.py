"""Storage-specific exception hierarchy."""

from api.exceptions import BeCoMeAPIError


class StorageError(BeCoMeAPIError):
    """Base exception for storage operations."""


class StorageConfigurationError(StorageError):
    """Raised when storage is not properly configured."""


class StorageUploadError(StorageError):
    """Raised when file upload fails."""


class StorageDeleteError(StorageError):
    """Raised when file deletion fails."""
