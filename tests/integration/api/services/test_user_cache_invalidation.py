"""Mutations invalidate the cached user snapshot."""

from api.services.user_cache import CachedUserData, InMemoryUserCache
from api.services.user_service import UserService


def test_update_user_invalidates_cache(session):
    cache = InMemoryUserCache()
    service = UserService(session, user_cache=cache)
    user = service.create_user(
        email="u@example.com", password="pw-123456", first_name="U", last_name="Ser"
    )
    cache.set(CachedUserData.from_user(user), ttl_seconds=60)

    service.update_user(user, first_name="Changed")

    assert cache.get(user.id) is None
