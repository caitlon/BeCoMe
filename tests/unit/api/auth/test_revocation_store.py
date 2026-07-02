"""Tests for the RevocationStore in-memory implementation."""

from datetime import UTC, datetime
from uuid import uuid4

import fakeredis
import pytest
import redis

from api.auth.revocation_store import (
    InMemoryRevocationStore,
    RedisRevocationStore,
    RevocationStore,
    RevocationStoreError,
    get_revocation_store,
)


def test_revoked_jti_is_reported_revoked():
    store = InMemoryRevocationStore()
    store.revoke_jti("jti-1", ttl_seconds=3600)
    assert store.is_jti_revoked("jti-1") is True


def test_unknown_jti_is_not_revoked():
    store = InMemoryRevocationStore()
    assert store.is_jti_revoked("nope") is False


def test_expired_jti_is_not_revoked_and_is_purged():
    store = InMemoryRevocationStore()
    store.revoke_jti("jti-x", ttl_seconds=-1)  # already expired
    assert store.is_jti_revoked("jti-x") is False


def test_valid_after_roundtrip():
    store = InMemoryRevocationStore()
    uid = uuid4()
    assert store.get_user_valid_after(uid) is None
    ts = datetime.now(UTC)
    store.set_user_valid_after(uid, ts)
    assert store.get_user_valid_after(uid) == ts


def test_get_revocation_store_returns_singleton():
    first = get_revocation_store()
    second = get_revocation_store()
    assert first is second
    assert isinstance(first, RevocationStore)


def test_redis_store_revoke_and_check():
    store = RedisRevocationStore(fakeredis.FakeStrictRedis())
    store.revoke_jti("jti-1", 3600)
    assert store.is_jti_revoked("jti-1") is True
    assert store.is_jti_revoked("other") is False


def test_redis_store_valid_after_roundtrip():
    store = RedisRevocationStore(fakeredis.FakeStrictRedis())
    uid = uuid4()
    assert store.get_user_valid_after(uid) is None
    ts = datetime.now(UTC)
    store.set_user_valid_after(uid, ts)
    assert store.get_user_valid_after(uid) == ts


def test_redis_error_raises_store_unavailable():
    class Boom:
        def exists(self, *_args):
            raise redis.RedisError("down")

    with pytest.raises(RevocationStoreError):
        RedisRevocationStore(Boom()).is_jti_revoked("x")
