"""Tests for per-address throttling of the emails an unauthenticated caller triggers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import fakeredis
import redis

from api.auth import email_throttle
from api.auth.email_throttle import (
    RESET_KEY_PREFIX,
    VERIFICATION_KEY_PREFIX,
    InMemoryEmailSendThrottle,
    RedisEmailSendThrottle,
)


class TestInMemoryEmailSendThrottle:
    """The in-memory throttle caps emails per address and fails safe."""

    def test_allows_first_send_then_blocks_within_cooldown(self):
        throttle = InMemoryEmailSendThrottle(cooldown_seconds=3600, daily_cap=5)
        assert throttle.allow("user@example.com") is True
        assert throttle.allow("user@example.com") is False

    def test_enforces_daily_cap(self):
        # No cooldown, so only the daily cap gates the rapid sends.
        throttle = InMemoryEmailSendThrottle(cooldown_seconds=0, daily_cap=3)
        outcomes = [throttle.allow("user@example.com") for _ in range(4)]
        assert outcomes == [True, True, True, False]

    def test_tracks_addresses_independently(self):
        throttle = InMemoryEmailSendThrottle(cooldown_seconds=3600)
        assert throttle.allow("a@example.com") is True
        assert throttle.allow("b@example.com") is True

    def test_identifier_is_case_insensitive(self):
        throttle = InMemoryEmailSendThrottle(cooldown_seconds=3600)
        assert throttle.allow("User@Example.com") is True
        assert throttle.allow("user@example.com") is False

    def test_two_instances_do_not_share_a_budget(self):
        # Each flow holds its own instance, which is what keeps the in-memory backend
        # from needing the key prefix the Redis one takes.
        reset = InMemoryEmailSendThrottle(cooldown_seconds=3600)
        verification = InMemoryEmailSendThrottle(cooldown_seconds=3600)
        assert reset.allow("user@example.com") is True
        assert verification.allow("user@example.com") is True

    def test_record_spends_a_slot_without_asking_for_one(self):
        """A send that must happen anyway still has to cost the address its allowance.

        Without this the caller that always mails would leave a clean budget behind,
        and a second, back-to-back request would mail again where a gated one had
        already gone quiet -- which is the timing difference the shared budget hides.
        """
        throttle = InMemoryEmailSendThrottle(cooldown_seconds=3600)
        throttle.record("user@example.com")
        assert throttle.allow("user@example.com") is False

    def test_record_is_never_denied(self):
        """Recording past an exhausted budget still records, it does not refuse."""
        throttle = InMemoryEmailSendThrottle(cooldown_seconds=0, daily_cap=1)
        assert throttle.allow("user@example.com") is True
        assert throttle.allow("user@example.com") is False
        throttle.record("user@example.com")
        assert throttle.allow("user@example.com") is False


class TestRedisEmailSendThrottle:
    """The Redis throttle shares state across replicas and fails open."""

    def test_allows_first_send_then_blocks_within_cooldown(self):
        throttle = RedisEmailSendThrottle(
            fakeredis.FakeStrictRedis(), key_prefix=RESET_KEY_PREFIX, cooldown_seconds=3600
        )
        assert throttle.allow("user@example.com") is True
        assert throttle.allow("user@example.com") is False

    def test_enforces_daily_cap(self):
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, cooldown_seconds=60, daily_cap=2
        )
        outcomes = []
        for _ in range(3):
            outcomes.append(throttle.allow("user@example.com"))
            # Simulate the per-send cooldown elapsing so only the daily cap gates.
            for key in fake.keys("reset:cooldown:*"):
                fake.delete(key)
        assert outcomes == [True, True, False]

    def test_prefixes_keep_the_two_flows_independent(self):
        """One Redis, two flows: spending the reset budget must not spend the other."""
        fake = fakeredis.FakeStrictRedis()
        reset = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, cooldown_seconds=3600, daily_cap=1
        )
        verification = RedisEmailSendThrottle(
            fake, key_prefix=VERIFICATION_KEY_PREFIX, cooldown_seconds=3600, daily_cap=1
        )

        assert reset.allow("user@example.com") is True
        assert verification.allow("user@example.com") is True
        assert reset.allow("user@example.com") is False
        assert verification.allow("user@example.com") is False

    def test_record_spends_a_slot_without_asking_for_one(self):
        """The always-mails caller writes the same keys a gated send would."""
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=VERIFICATION_KEY_PREFIX, cooldown_seconds=3600
        )

        throttle.record("user@example.com")

        assert fake.keys("verify:cooldown:*")
        assert fake.keys("verify:daily:*")
        assert throttle.allow("user@example.com") is False

    def test_record_restarts_the_cooldown_rather_than_consulting_it(self):
        """Recording twice is not an error, and each one counts against the daily cap."""
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, cooldown_seconds=3600, daily_cap=2
        )

        throttle.record("user@example.com")
        throttle.record("user@example.com")

        digest = next(iter(fake.keys("reset:daily:*")))
        assert int(fake.get(digest)) == 2

    def test_fails_open_when_store_is_unavailable(self):
        class Boom:
            def set(self, *_args, **_kwargs):
                raise redis.RedisError("down")

        # A store outage must not suppress a legitimate email.
        throttle = RedisEmailSendThrottle(Boom(), key_prefix=RESET_KEY_PREFIX)
        assert throttle.allow("user@example.com") is True

    def test_record_swallows_a_store_outage(self):
        """A store fault must not turn into an error on a request already decided."""

        class Boom:
            def set(self, *_args, **_kwargs):
                raise redis.RedisError("down")

        RedisEmailSendThrottle(Boom(), key_prefix=RESET_KEY_PREFIX).record("user@example.com")


class TestThrottleFactories:
    """The factories select the Redis backend when a redis_url is configured."""

    def test_reset_factory_uses_redis_when_configured(self):
        email_throttle.get_reset_email_throttle.cache_clear()
        with (
            patch.object(
                email_throttle,
                "get_settings",
                return_value=SimpleNamespace(redis_url="redis://cache:6379/0"),
            ),
            patch.object(email_throttle.redis, "from_url", return_value=MagicMock()) as from_url,
        ):
            throttle = email_throttle.get_reset_email_throttle()
        email_throttle.get_reset_email_throttle.cache_clear()

        assert isinstance(throttle, RedisEmailSendThrottle)
        from_url.assert_called_once()

    def test_verification_factory_uses_its_own_key_prefix(self):
        """The verification flow must not write into the password-reset keyspace."""
        fake = fakeredis.FakeStrictRedis()
        email_throttle.get_verification_email_throttle.cache_clear()
        with (
            patch.object(
                email_throttle,
                "get_settings",
                return_value=SimpleNamespace(redis_url="redis://cache:6379/0"),
            ),
            patch.object(email_throttle.redis, "from_url", return_value=fake),
        ):
            throttle = email_throttle.get_verification_email_throttle()
        email_throttle.get_verification_email_throttle.cache_clear()

        assert throttle.allow("user@example.com") is True
        assert fake.keys("verify:cooldown:*")
        assert fake.keys("reset:cooldown:*") == []

    def test_falls_back_to_the_in_memory_backend_without_redis(self):
        email_throttle.get_verification_email_throttle.cache_clear()
        with patch.object(
            email_throttle, "get_settings", return_value=SimpleNamespace(redis_url="")
        ):
            throttle = email_throttle.get_verification_email_throttle()
        email_throttle.get_verification_email_throttle.cache_clear()

        assert isinstance(throttle, InMemoryEmailSendThrottle)
