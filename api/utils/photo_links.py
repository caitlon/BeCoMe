"""Build public proxy URLs for user profile photos."""

from uuid import UUID

from api.config import get_settings


def build_photo_url(user_id: str | UUID, photo_key: str | None) -> str | None:
    """Build the public proxy URL for a user's profile photo.

    The API serves photos from a private bucket through
    ``GET /api/v1/users/{user_id}/photo``. A cache-buster derived from the
    stored object key changes the URL whenever the photo is replaced, so
    browsers re-fetch a new avatar instead of showing a cached one.

    :param user_id: Owner user id.
    :param photo_key: Stored object key, or None when no photo is set.
    :return: Absolute proxy URL, or None when no photo is set.
    """
    if not photo_key:
        return None
    base = get_settings().api_public_url.rstrip("/")
    return f"{base}/api/v1/users/{user_id}/photo?v={_cache_buster(photo_key)}"


def _cache_buster(photo_key: str) -> str:
    """Derive a short, stable cache-buster token from the object key.

    :param photo_key: Stored object key like ``profiles/<id>/<random>.<ext>``.
    :return: The random key segment without its extension.
    """
    tail = photo_key.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]
