"""The auth dependency serves cached users and bypasses the DB on a hit."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from api.services.user_cache import CachedUserData, get_user_cache


@pytest.mark.asyncio
async def test_cache_hit_skips_the_database(monkeypatch):
    """A pre-warmed cache entry satisfies get_current_user without a DB call."""
    from api.auth import dependencies as deps

    user_id = uuid4()
    cached = CachedUserData(
        id=user_id,
        email="hit@example.com",
        first_name="Hit",
        last_name="User",
        photo_url=None,
        created_at=datetime.now(UTC),
    )
    get_user_cache.cache_clear()
    get_user_cache().set(cached, ttl_seconds=60)

    monkeypatch.setattr(deps, "decode_access_token", lambda token, store: user_id)

    def _boom(self, _id):
        raise AssertionError("DB must not be hit on a cache hit")

    monkeypatch.setattr("api.services.user_service.UserService.get_by_id", _boom)

    user = await deps.get_current_user(
        token="t", session=object(), store=object(), cache=get_user_cache()
    )
    assert user.id == user_id
    assert user.email == "hit@example.com"
    assert user.hashed_password == ""


class _MismatchedCache:
    """Cache stub returning a snapshot whose id disagrees with the queried key.

    A real ``InMemoryUserCache.set`` always keys an entry by the snapshot's own
    ``id``, so it cannot represent key/value drift. This stub stands in for a
    tampered or corrupted backend that returns the wrong snapshot for a key.
    """

    def __init__(self, snapshot: CachedUserData) -> None:
        self._snapshot = snapshot

    def get(self, user_id):
        """Return the fixed snapshot regardless of the requested id."""
        return self._snapshot

    def set(self, data, ttl_seconds):
        """No-op: the miss path's cache write is not under test here."""

    def invalidate(self, user_id):
        """No-op: invalidation is not under test here."""


@pytest.mark.asyncio
async def test_cache_id_mismatch_falls_through_to_the_database(monkeypatch):
    """A cached snapshot whose id disagrees with the token subject is not served."""
    from api.auth import dependencies as deps
    from api.db.models import User

    token_user_id = uuid4()
    other_user_id = uuid4()
    mismatched = CachedUserData(
        id=other_user_id,
        email="mismatched@example.com",
        first_name="Mismatched",
        last_name="User",
        photo_url=None,
        created_at=datetime.now(UTC),
    )

    monkeypatch.setattr(deps, "decode_access_token", lambda token, store: token_user_id)

    db_user = User(
        id=token_user_id,
        email="db@example.com",
        hashed_password="hashed",
        first_name="DB",
        last_name="User",
    )

    def _fake_get_by_id(self, _id):
        return db_user

    monkeypatch.setattr("api.services.user_service.UserService.get_by_id", _fake_get_by_id)

    user = await deps.get_current_user(
        token="t", session=object(), store=object(), cache=_MismatchedCache(mismatched)
    )
    assert user.id == token_user_id
    assert user.email == "db@example.com"
