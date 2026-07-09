"""Redis-backed cache for the per-request user lookup."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
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
