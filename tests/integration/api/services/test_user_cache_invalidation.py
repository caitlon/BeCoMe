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


def test_change_password_invalidates_cache(session):
    """change_password drops the cached snapshot after the hash is updated."""
    cache = InMemoryUserCache()
    service = UserService(session, user_cache=cache)
    user = service.create_user(
        email="u@example.com", password="pw-123456", first_name="U", last_name="Ser"
    )
    cache.set(CachedUserData.from_user(user), ttl_seconds=60)

    service.change_password(user, current_password="pw-123456", new_password="pw-654321")

    assert cache.get(user.id) is None


def test_update_photo_url_invalidates_cache(session):
    """update_photo_url drops the cached snapshot after the photo key is updated."""
    cache = InMemoryUserCache()
    service = UserService(session, user_cache=cache)
    user = service.create_user(
        email="u@example.com", password="pw-123456", first_name="U", last_name="Ser"
    )
    cache.set(CachedUserData.from_user(user), ttl_seconds=60)

    service.update_photo_url(user, "some/key.jpg")

    assert cache.get(user.id) is None


def test_delete_user_invalidates_cache(session):
    """delete_user drops the cached snapshot after the account is removed."""
    cache = InMemoryUserCache()
    service = UserService(session, user_cache=cache)
    user = service.create_user(
        email="u@example.com", password="pw-123456", first_name="U", last_name="Ser"
    )
    cache.set(CachedUserData.from_user(user), ttl_seconds=60)

    service.delete_user(user)

    assert cache.get(user.id) is None
