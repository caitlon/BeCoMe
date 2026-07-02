"""Tests for per-account login throttling."""

import fakeredis
import redis
from api.auth.login_throttle import InMemoryLoginThrottle, RedisLoginThrottle


class TestInMemoryLoginThrottle:
    """The in-memory throttle locks an account after too many failures."""

    def test_locks_after_threshold_failures(self):
        throttle = InMemoryLoginThrottle(max_failures=3, window_seconds=3600)
        assert throttle.is_locked("user@example.com") is False
        for _ in range(3):
            throttle.record_failure("user@example.com")
        assert throttle.is_locked("user@example.com") is True

    def test_reset_clears_failures(self):
        throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        throttle.record_failure("user@example.com")
        throttle.record_failure("user@example.com")
        assert throttle.is_locked("user@example.com") is True
        throttle.reset("user@example.com")
        assert throttle.is_locked("user@example.com") is False

    def test_tracks_accounts_independently(self):
        throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        throttle.record_failure("victim@example.com")
        throttle.record_failure("victim@example.com")
        assert throttle.is_locked("victim@example.com") is True
        assert throttle.is_locked("other@example.com") is False

    def test_identifier_is_case_insensitive(self):
        throttle = InMemoryLoginThrottle(max_failures=2, window_seconds=3600)
        throttle.record_failure("User@Example.com")
        throttle.record_failure("user@example.com")
        assert throttle.is_locked("USER@EXAMPLE.COM") is True


class TestRedisLoginThrottle:
    """The Redis throttle shares lockout state across replicas and fails open."""

    def test_locks_after_threshold_then_resets(self):
        throttle = RedisLoginThrottle(
            fakeredis.FakeStrictRedis(), max_failures=3, window_seconds=3600
        )
        for _ in range(3):
            throttle.record_failure("user@example.com")
        assert throttle.is_locked("user@example.com") is True
        throttle.reset("user@example.com")
        assert throttle.is_locked("user@example.com") is False

    def test_fails_open_when_store_is_unavailable(self):
        class Boom:
            def get(self, *_args):
                raise redis.RedisError("down")

        # A store outage must not lock every user out of logging in.
        assert RedisLoginThrottle(Boom()).is_locked("user@example.com") is False
