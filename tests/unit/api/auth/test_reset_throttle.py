"""Tests for per-address password-reset email throttling."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import fakeredis
import redis

from api.auth import reset_throttle
from api.auth.reset_throttle import InMemoryResetEmailThrottle, RedisResetEmailThrottle


class TestInMemoryResetEmailThrottle:
    """The in-memory throttle caps reset emails per address and fails safe."""

    def test_allows_first_send_then_blocks_within_cooldown(self):
        throttle = InMemoryResetEmailThrottle(cooldown_seconds=3600, daily_cap=5)
        assert throttle.allow("user@example.com") is True
        assert throttle.allow("user@example.com") is False

    def test_enforces_daily_cap(self):
        # No cooldown, so only the daily cap gates the rapid sends.
        throttle = InMemoryResetEmailThrottle(cooldown_seconds=0, daily_cap=3)
        outcomes = [throttle.allow("user@example.com") for _ in range(4)]
        assert outcomes == [True, True, True, False]

    def test_tracks_addresses_independently(self):
        throttle = InMemoryResetEmailThrottle(cooldown_seconds=3600)
        assert throttle.allow("a@example.com") is True
        assert throttle.allow("b@example.com") is True

    def test_identifier_is_case_insensitive(self):
        throttle = InMemoryResetEmailThrottle(cooldown_seconds=3600)
        assert throttle.allow("User@Example.com") is True
        assert throttle.allow("user@example.com") is False


class TestRedisResetEmailThrottle:
    """The Redis throttle shares state across replicas and fails open."""

    def test_allows_first_send_then_blocks_within_cooldown(self):
        throttle = RedisResetEmailThrottle(fakeredis.FakeStrictRedis(), cooldown_seconds=3600)
        assert throttle.allow("user@example.com") is True
        assert throttle.allow("user@example.com") is False

    def test_enforces_daily_cap(self):
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisResetEmailThrottle(fake, cooldown_seconds=60, daily_cap=2)
        outcomes = []
        for _ in range(3):
            outcomes.append(throttle.allow("user@example.com"))
            # Simulate the per-send cooldown elapsing so only the daily cap gates.
            for key in fake.keys("reset:cooldown:*"):
                fake.delete(key)
        assert outcomes == [True, True, False]

    def test_fails_open_when_store_is_unavailable(self):
        class Boom:
            def set(self, *_args, **_kwargs):
                raise redis.RedisError("down")

        # A store outage must not suppress a legitimate reset email.
        assert RedisResetEmailThrottle(Boom()).allow("user@example.com") is True


class TestGetResetEmailThrottle:
    """The factory selects the Redis backend when a redis_url is configured."""

    def test_uses_redis_when_configured(self):
        reset_throttle.get_reset_email_throttle.cache_clear()
        with (
            patch.object(
                reset_throttle,
                "get_settings",
                return_value=SimpleNamespace(redis_url="redis://cache:6379/0"),
            ),
            patch.object(reset_throttle.redis, "from_url", return_value=MagicMock()) as from_url,
        ):
            throttle = reset_throttle.get_reset_email_throttle()
        reset_throttle.get_reset_email_throttle.cache_clear()

        assert isinstance(throttle, RedisResetEmailThrottle)
        from_url.assert_called_once()
