"""Tests for the RevocationStore in-memory implementation."""

from datetime import UTC, datetime
from uuid import uuid4

from api.auth.revocation_store import InMemoryRevocationStore


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
