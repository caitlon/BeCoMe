"""Deleting an account revokes its tokens (M2) and profile edits show immediately."""

from tests.integration.api.conftest import auth_header, register_and_login


def test_profile_update_is_visible_immediately(client):
    """A profile edit is served back on the very next GET, not a stale cache entry."""
    token = register_and_login(client, "cache-fresh@example.com")
    # Warm the profile cache first, so the update runs against whatever dependency the
    # write endpoint uses while a cache entry is live (transient on a cache hit).
    client.get("/api/v1/users/me", headers=auth_header(token))

    client.put("/api/v1/users/me", json={"first_name": "Renamed"}, headers=auth_header(token))
    me = client.get("/api/v1/users/me", headers=auth_header(token))

    assert me.json()["first_name"] == "Renamed"


def test_delete_account_revokes_the_access_token(client):
    """A deleted account's token is rejected immediately, not served from cache (M2)."""
    token = register_and_login(client, "cache-delete@example.com")
    # Warm the profile cache first (e.g. the user viewed their own profile) so deletion
    # must cope with a live cache entry instead of the common cold-cache path.
    client.get("/api/v1/users/me", headers=auth_header(token))

    resp = client.delete("/api/v1/users/me", headers=auth_header(token))
    assert resp.status_code == 204

    # The same token must now be rejected (valid_after cutoff), not served from cache.
    after = client.get("/api/v1/users/me", headers=auth_header(token))
    assert after.status_code == 401
