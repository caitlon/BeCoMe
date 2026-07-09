"""Tests for the user profile cache."""

from datetime import UTC, datetime
from uuid import uuid4

from api.db.models import User
from api.services.user_cache import CachedUserData


def _sample_user() -> User:
    return User(
        id=uuid4(),
        email="alice@example.com",
        hashed_password="secret-hash",
        first_name="Alice",
        last_name="Smith",
        photo_url="key/photo.jpg",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_cached_user_data_roundtrips_through_json():
    user = _sample_user()
    data = CachedUserData.from_user(user)
    restored = CachedUserData.from_json(data.to_json())
    assert restored == data
    assert restored.email == "alice@example.com"


def test_cached_user_data_never_serializes_hashed_password():
    data = CachedUserData.from_user(_sample_user())
    assert "secret-hash" not in data.to_json()


def test_to_user_rebuilds_user_with_empty_hash():
    user = _sample_user()
    restored = CachedUserData.from_user(user).to_user()
    assert isinstance(restored, User)
    assert restored.id == user.id
    assert restored.email == user.email
    assert restored.first_name == user.first_name
    assert restored.hashed_password == ""


def test_in_memory_cache_get_set_invalidate():
    """Set, get, and invalidate a cache entry."""
    from api.services.user_cache import InMemoryUserCache

    cache = InMemoryUserCache()
    data = CachedUserData.from_user(_sample_user())
    assert cache.get(data.id) is None
    cache.set(data, ttl_seconds=60)
    assert cache.get(data.id) == data
    cache.invalidate(data.id)
    assert cache.get(data.id) is None


def test_in_memory_cache_expires_entries():
    """Expired entries return None on get."""
    from api.services.user_cache import InMemoryUserCache

    cache = InMemoryUserCache()
    data = CachedUserData.from_user(_sample_user())
    cache.set(data, ttl_seconds=-1)  # already expired
    assert cache.get(data.id) is None


def test_in_memory_cache_satisfies_protocol():
    """InMemoryUserCache implements the UserCacheStore protocol."""
    from api.services.user_cache import InMemoryUserCache, UserCacheStore

    assert isinstance(InMemoryUserCache(), UserCacheStore)
