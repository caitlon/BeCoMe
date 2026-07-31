"""Tests for per-account login and activation-guess throttling."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import fakeredis
import redis

from api.auth import login_throttle
from api.auth.login_throttle import (
    ACTIVATION_KEY_PREFIX,
    LOGIN_KEY_PREFIX,
    InMemoryLoginThrottle,
    RedisLoginThrottle,
)


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

    def test_two_instances_do_not_share_a_budget(self):
        # Each flow holds its own instance, which is what keeps the in-memory backend
        # from needing the key prefix the Redis one takes.
        login = InMemoryLoginThrottle(max_failures=1, window_seconds=3600)
        activation = InMemoryLoginThrottle(max_failures=1, window_seconds=3600)
        login.record_failure("user@example.com")
        assert login.is_locked("user@example.com") is True
        assert activation.is_locked("user@example.com") is False


class TestRedisLoginThrottle:
    """The Redis throttle shares lockout state across replicas and fails open."""

    def test_locks_after_threshold_then_resets(self):
        throttle = RedisLoginThrottle(
            fakeredis.FakeStrictRedis(),
            key_prefix=LOGIN_KEY_PREFIX,
            max_failures=3,
            window_seconds=3600,
        )
        for _ in range(3):
            throttle.record_failure("user@example.com")
        assert throttle.is_locked("user@example.com") is True
        throttle.reset("user@example.com")
        assert throttle.is_locked("user@example.com") is False

    def test_prefixes_keep_login_and_activation_independent(self):
        """One Redis, two flows: locking one must not read or write the other's count."""
        fake = fakeredis.FakeStrictRedis()
        login = RedisLoginThrottle(fake, key_prefix=LOGIN_KEY_PREFIX, max_failures=1)
        activation = RedisLoginThrottle(fake, key_prefix=ACTIVATION_KEY_PREFIX, max_failures=1)

        login.record_failure("user@example.com")

        assert login.is_locked("user@example.com") is True
        assert activation.is_locked("user@example.com") is False

    def test_fails_open_when_store_is_unavailable(self):
        class Boom:
            def get(self, *_args):
                raise redis.RedisError("down")

        # A store outage must not lock every user out.
        throttle = RedisLoginThrottle(Boom(), key_prefix=LOGIN_KEY_PREFIX)
        assert throttle.is_locked("user@example.com") is False

    def test_record_failure_swallows_a_store_outage(self):
        """A store fault while recording must not turn into an error either."""

        class Boom:
            def pipeline(self):
                raise redis.RedisError("down")

        RedisLoginThrottle(Boom(), key_prefix=LOGIN_KEY_PREFIX).record_failure("user@example.com")

    def test_reset_swallows_a_store_outage(self):
        class Boom:
            def delete(self, *_args):
                raise redis.RedisError("down")

        RedisLoginThrottle(Boom(), key_prefix=LOGIN_KEY_PREFIX).reset("user@example.com")


class TestThrottleFactories:
    """The factories select the Redis backend when configured, one prefix per flow."""

    def test_login_factory_uses_redis_when_configured(self):
        login_throttle.get_login_throttle.cache_clear()
        with (
            patch.object(
                login_throttle,
                "get_settings",
                return_value=SimpleNamespace(redis_url="redis://cache:6379/0"),
            ),
            patch.object(login_throttle.redis, "from_url", return_value=MagicMock()) as from_url,
        ):
            throttle = login_throttle.get_login_throttle()
        login_throttle.get_login_throttle.cache_clear()

        assert isinstance(throttle, RedisLoginThrottle)
        from_url.assert_called_once()

    def test_activation_factory_uses_its_own_key_prefix(self):
        """The activation flow must not read or write the login keyspace."""
        fake = fakeredis.FakeStrictRedis()
        login_throttle.get_activation_throttle.cache_clear()
        with (
            patch.object(
                login_throttle,
                "get_settings",
                return_value=SimpleNamespace(redis_url="redis://cache:6379/0"),
            ),
            patch.object(login_throttle.redis, "from_url", return_value=fake),
        ):
            throttle = login_throttle.get_activation_throttle()
        login_throttle.get_activation_throttle.cache_clear()

        throttle.record_failure("user@example.com")

        assert fake.keys("activation:fail:*")
        assert fake.keys("login:fail:*") == []

    def test_falls_back_to_the_in_memory_backend_without_redis(self):
        login_throttle.get_activation_throttle.cache_clear()
        with patch.object(
            login_throttle, "get_settings", return_value=SimpleNamespace(redis_url="")
        ):
            throttle = login_throttle.get_activation_throttle()
        login_throttle.get_activation_throttle.cache_clear()

        assert isinstance(throttle, InMemoryLoginThrottle)
