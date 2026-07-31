"""Tests for the user profile cache."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from api.db.models import User
from api.services.user_cache import CachedUserData


def _sample_user(email_verified_at: datetime | None = None) -> User:
    return User(
        id=uuid4(),
        email="alice@example.com",
        hashed_password="secret-hash",
        first_name="Alice",
        last_name="Smith",
        photo_url="key/photo.jpg",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        email_verified_at=email_verified_at,
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


def test_cached_user_data_roundtrip_preserves_email_verified_at_when_set():
    """A verified user's timestamp survives a to_json/from_json roundtrip."""
    verified_at = datetime(2026, 1, 5, tzinfo=UTC)
    user = _sample_user(email_verified_at=verified_at)
    data = CachedUserData.from_user(user)
    restored = CachedUserData.from_json(data.to_json())
    assert restored == data
    assert restored.email_verified_at == verified_at


def test_cached_user_data_roundtrip_preserves_email_verified_at_when_none():
    """An unverified user's None survives a to_json/from_json roundtrip."""
    user = _sample_user(email_verified_at=None)
    data = CachedUserData.from_user(user)
    restored = CachedUserData.from_json(data.to_json())
    assert restored == data
    assert restored.email_verified_at is None


def test_from_json_missing_email_verified_at_key_raises_value_error():
    """A payload shaped like the old v1 cache entry lacks the key and must miss, not crash."""
    payload = json.dumps(
        {
            "id": str(uuid4()),
            "email": "old@example.com",
            "first_name": "Old",
            "last_name": "Shape",
            "photo_url": None,
            "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        }
    )
    with pytest.raises(ValueError, match="invalid cached user data"):
        CachedUserData.from_json(payload)


def test_to_user_rebuilds_user_with_empty_hash():
    user = _sample_user()
    restored = CachedUserData.from_user(user).to_user()
    assert isinstance(restored, User)
    assert restored.id == user.id
    assert restored.email == user.email
    assert restored.first_name == user.first_name
    assert restored.hashed_password == ""


def test_to_user_carries_email_verified_at():
    """to_user() threads email_verified_at through to the rebuilt transient User."""
    verified_at = datetime(2026, 1, 5, tzinfo=UTC)
    user = _sample_user(email_verified_at=verified_at)
    restored = CachedUserData.from_user(user).to_user()
    assert restored.email_verified_at == verified_at


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


def test_caches_skip_nonpositive_ttl():
    """A TTL below 1 is not stored by either backend, giving a consistent miss."""
    import fakeredis

    from api.services.user_cache import InMemoryUserCache, RedisUserCache

    data = CachedUserData.from_user(_sample_user())

    in_memory = InMemoryUserCache()
    in_memory.set(data, ttl_seconds=0)
    assert in_memory.get(data.id) is None

    redis_cache = RedisUserCache(fakeredis.FakeStrictRedis())
    redis_cache.set(data, ttl_seconds=0)
    assert redis_cache.get(data.id) is None


def test_in_memory_cache_satisfies_protocol():
    """InMemoryUserCache implements the UserCacheStore protocol."""
    from api.services.user_cache import InMemoryUserCache, UserCacheStore

    assert isinstance(InMemoryUserCache(), UserCacheStore)


def test_redis_cache_roundtrip_and_key():
    """Redis cache roundtrips data and stores with correct TTL."""

    import fakeredis

    from api.services.user_cache import RedisUserCache

    client = fakeredis.FakeStrictRedis()
    cache = RedisUserCache(client)
    data = CachedUserData.from_user(_sample_user())
    cache.set(data, ttl_seconds=60)
    assert cache.get(data.id) == data
    assert client.ttl(f"user:profile:v2:{data.id}") > 0


def test_redis_cache_invalidate_removes_key():
    """Invalidation removes the key from cache."""

    import fakeredis

    from api.services.user_cache import RedisUserCache

    client = fakeredis.FakeStrictRedis()
    cache = RedisUserCache(client)
    data = CachedUserData.from_user(_sample_user())
    cache.set(data, ttl_seconds=60)
    cache.invalidate(data.id)
    assert cache.get(data.id) is None


def test_redis_cache_is_fail_open_on_errors():
    """Redis errors are logged and swallowed, returning None or no-op."""
    from unittest.mock import MagicMock

    import fakeredis
    import redis

    from api.services.user_cache import RedisUserCache

    client = MagicMock(spec=fakeredis.FakeStrictRedis)
    client.get.side_effect = redis.RedisError("down")
    client.set.side_effect = redis.RedisError("down")
    client.delete.side_effect = redis.RedisError("down")
    cache = RedisUserCache(client)
    data = CachedUserData.from_user(_sample_user())
    # None of these raise:
    assert cache.get(data.id) is None
    cache.set(data, ttl_seconds=60)
    cache.invalidate(data.id)


def test_redis_cache_treats_corrupted_value_as_miss():
    """Corrupted cached values (non-JSON, null, number, invalid UTF-8) return None."""
    import fakeredis

    from api.services.user_cache import RedisUserCache

    client = fakeredis.FakeStrictRedis()
    cache = RedisUserCache(client)
    key_template = RedisUserCache._key

    # Test non-JSON bytes
    user_id = uuid4()
    client.set(key_template(user_id), b"not json")
    assert cache.get(user_id) is None

    # Test JSON null
    user_id = uuid4()
    client.set(key_template(user_id), b"null")
    assert cache.get(user_id) is None

    # Test JSON number
    user_id = uuid4()
    client.set(key_template(user_id), b"42")
    assert cache.get(user_id) is None

    # Test invalid UTF-8
    user_id = uuid4()
    client.set(key_template(user_id), b"\xff\xfe")
    assert cache.get(user_id) is None

    # Test wrong-typed id (integer instead of string)
    user_id = uuid4()
    client.set(
        key_template(user_id),
        b'{"id": 42, "email": "e@x.com", "first_name": "A", "last_name": "B", "photo_url": null, '
        b'"created_at": "2026-01-01T00:00:00+00:00", "email_verified_at": null}',
    )
    assert cache.get(user_id) is None

    # Test unparseable uuid
    user_id = uuid4()
    client.set(
        key_template(user_id),
        b'{"id": "not-a-uuid", "email": "e@x.com", "first_name": "A", "last_name": "B", '
        b'"photo_url": null, "created_at": "2026-01-01T00:00:00+00:00", "email_verified_at": null}',
    )
    assert cache.get(user_id) is None


def test_redis_cache_satisfies_protocol():
    """RedisUserCache implements the UserCacheStore protocol."""
    import fakeredis

    from api.services.user_cache import RedisUserCache, UserCacheStore

    assert isinstance(RedisUserCache(fakeredis.FakeStrictRedis()), UserCacheStore)


def test_ttl_setting_defaults_to_60():
    """TTL setting defaults to 60 seconds."""
    from api.config import get_settings

    assert get_settings().user_cache_ttl_seconds == 60


def test_get_user_cache_is_singleton():
    """get_user_cache returns the same instance (singleton pattern)."""
    from api.services.user_cache import UserCacheStore, get_user_cache

    get_user_cache.cache_clear()
    first = get_user_cache()
    second = get_user_cache()
    assert first is second
    assert isinstance(first, UserCacheStore)
