"""Redis-backed cache for the per-request user lookup."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable
from uuid import UUID

from api.db.models import User


@dataclass(frozen=True)
class CachedUserData:
    """Serializable snapshot of a user's non-secret profile fields.

    Deliberately not an ORM object and deliberately without ``hashed_password``:
    it is what lives in Redis, and ``to_user`` rebuilds a transient ``User`` from it.
    """

    id: UUID
    email: str
    first_name: str
    last_name: str
    photo_url: str | None
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> CachedUserData:
        """Build a snapshot from an ORM user.

        :param user: The database user.
        :return: A cacheable snapshot without the password hash.
        """
        return cls(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            photo_url=user.photo_url,
            created_at=user.created_at,
        )

    def to_json(self) -> str:
        """Serialize to a JSON string for Redis.

        :return: JSON text; ``hashed_password`` is never included.
        """
        return json.dumps(
            {
                "id": str(self.id),
                "email": self.email,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "photo_url": self.photo_url,
                "created_at": self.created_at.isoformat(),
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> CachedUserData:
        """Parse a JSON string produced by :meth:`to_json`.

        :param raw: JSON text from Redis.
        :return: The reconstructed snapshot.
        :raises ValueError: If the text is not valid JSON for this shape.
        :raises KeyError: If a required field is missing.
        """
        data = json.loads(raw)
        return cls(
            id=UUID(data["id"]),
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            photo_url=data["photo_url"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    def to_user(self) -> User:
        """Rebuild a transient ``User`` (not bound to any session).

        ``hashed_password`` is set to an empty string: read paths never read it,
        and write paths take a fresh session-bound user instead.

        :return: A transient ``User`` carrying the cached profile fields.
        """
        return User(
            id=self.id,
            email=self.email,
            hashed_password="",
            first_name=self.first_name,
            last_name=self.last_name,
            photo_url=self.photo_url,
            created_at=self.created_at,
        )


@runtime_checkable
class UserCacheStore(Protocol):
    """Cache backend for the per-request user profile lookup."""

    def get(self, user_id: UUID) -> CachedUserData | None:
        """Return the cached snapshot if present and unexpired, else ``None``.

        :param user_id: The user ID to look up.
        :return: The cached snapshot or ``None`` if absent or expired.
        """
        ...

    def set(self, data: CachedUserData, ttl_seconds: int) -> None:
        """Store ``data`` under its own id for ``ttl_seconds``.

        :param data: The snapshot to cache.
        :param ttl_seconds: Time to live in seconds.
        """
        ...

    def invalidate(self, user_id: UUID) -> None:
        """Drop the cached snapshot for ``user_id`` if any.

        :param user_id: The user ID to invalidate.
        """
        ...


class InMemoryUserCache:
    """Process-local UserCacheStore for dev and tests (not shared across replicas)."""

    def __init__(self) -> None:
        self._entries: dict[UUID, tuple[CachedUserData, datetime]] = {}
        self._lock = threading.Lock()

    def get(self, user_id: UUID) -> CachedUserData | None:
        """Return the cached snapshot if present and unexpired, else ``None``.

        :param user_id: The user ID to look up.
        :return: The cached snapshot or ``None`` if absent or expired.
        """
        with self._lock:
            entry = self._entries.get(user_id)
            if entry is None:
                return None
            data, expires_at = entry
            if expires_at <= datetime.now(UTC):
                del self._entries[user_id]
                return None
            return data

    def set(self, data: CachedUserData, ttl_seconds: int) -> None:
        """Store ``data`` under its own id for ``ttl_seconds``.

        :param data: The snapshot to cache.
        :param ttl_seconds: Time to live in seconds.
        """
        expires_at = datetime.now(UTC) + timedelta(seconds=max(ttl_seconds, 0))
        with self._lock:
            self._entries[data.id] = (data, expires_at)

    def invalidate(self, user_id: UUID) -> None:
        """Drop the cached snapshot for ``user_id`` if any.

        :param user_id: The user ID to invalidate.
        """
        with self._lock:
            self._entries.pop(user_id, None)

    def clear(self) -> None:
        """Drop all cached snapshots (test helper).

        :return: None
        """
        with self._lock:
            self._entries.clear()
