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
    return f"{base}/api/v1/users/{user_id}/photo?v={photo_version(photo_key)}"


def photo_version(photo_key: str) -> str:
    """Derive the version token that identifies one stored photo.

    The photo route compares the ``v`` it was asked for against this, so the two
    must agree on what a version is: only a request naming the key currently on
    the account describes bytes that cannot change under it.

    :param photo_key: Stored object key like ``profiles/<id>/<random>.<ext>``.
    :return: The random key segment without its extension.
    """
    tail = photo_key.rsplit("/", 1)[-1]
    return tail.rsplit(".", 1)[0]
