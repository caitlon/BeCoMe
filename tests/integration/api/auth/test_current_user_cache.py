"""The auth dependency serves cached users and bypasses the DB on a hit."""

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
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
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
