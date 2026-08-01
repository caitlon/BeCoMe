"""Abstract storage interface for profile photo files."""

from abc import ABC, abstractmethod

from api.services.storage.stored_object import StoredObject


class StorageService(ABC):
    """File storage backend for profile photos, addressed by object key.

    Implementations store and retrieve objects by an opaque key. The key is
    persisted on the user record; presentation URLs are built separately so the
    stored value stays independent of any public host.
    """

    @abstractmethod
    def upload(self, content: bytes, content_type: str, user_id: str) -> str:
        """Store file bytes and return the generated object key.

        :param content: Raw file bytes (already validated).
        :param content_type: Validated MIME type.
        :param user_id: Owner user id, used to namespace the key.
        :return: Object key under which the file was stored.
        :raises StorageUploadError: If the upload fails.
        """

    @abstractmethod
    def open(self, key: str) -> StoredObject | None:
        """Open a stored object for reading, without downloading it.

        The returned handle owns a live connection to the backend, so the caller
        must either read it to the end or close it.

        :param key: Object key.
        :return: An open :class:`StoredObject`, or None when the object is absent.
        :raises StorageError: If the fetch fails for a reason other than absence.
        """

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a stored object by key.

        :param key: Object key.
        :return: True when a delete request was issued.
        :raises StorageDeleteError: If deletion fails.
        """
