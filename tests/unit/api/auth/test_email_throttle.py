"""Tests for per-address throttling of the emails an unauthenticated caller triggers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
import redis

from api.auth import email_throttle
from api.auth.email_throttle import (
    RESET_KEY_PREFIX,
    VERIFICATION_KEY_PREFIX,
    InMemoryEmailSendThrottle,
    RedisEmailSendThrottle,
)


class _DroppingClient:
    """A Redis client whose connection drops at a chosen point of the daily-counter update.

    ``incr`` applies and then drops, which is the gap the old INCR-then-EXPIRE pair left
    open. A pipeline carrying INCR applies its commands first when ``apply_pipeline`` is
    set (the reply is lost) and drops before reaching the server otherwise; other
    pipelines (the read in ``allow``) run normally.
    """

    def __init__(self, inner: fakeredis.FakeStrictRedis, *, apply_pipeline: bool) -> None:
        self._inner = inner
        self._apply_pipeline = apply_pipeline

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def incr(self, name: str, amount: int = 1) -> int:
        self._inner.incr(name, amount)
        raise redis.ConnectionError("dropped after INCR")

    def pipeline(self, transaction: bool = True):
        real = self._inner.pipeline(transaction=transaction)
        apply_pipeline = self._apply_pipeline

        class _Dropping:
            carries_incr = False

            def __getattr__(self, name: str):
                return getattr(real, name)

            def incr(self, *args, **kwargs):
                self.carries_incr = True
                return real.incr(*args, **kwargs)

            def execute(self):
                if not self.carries_incr:
                    return real.execute()
                # A pipeline outside a transaction would not be atomic, so the drop tests
                # must fail for one.
                assert transaction is True
                if apply_pipeline:
                    real.execute()
                raise redis.ConnectionError("dropped around EXEC")

        return _Dropping()


class _ExpireFails:
    """A Redis client whose EXPIRE always fails, as a drop right after the pipeline would."""

    def __init__(self, inner: fakeredis.FakeStrictRedis) -> None:
        self._inner = inner

    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def expire(self, *_args, **_kwargs):
        raise redis.ConnectionError("dropped before EXPIRE")


def _daily_key(fake: fakeredis.FakeStrictRedis, prefix: str) -> bytes:
    """Return the one daily counter key a flow holds, as the throttle named it."""
    (key,) = fake.keys(f"{prefix}:daily:*")
    return key


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
        already gone quiet, which is the timing difference the shared budget hides.
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

    def test_allow_gives_the_daily_counter_an_expiry(self):
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_window_seconds=3600
        )

        assert throttle.allow("user@example.com") is True

        key = _daily_key(fake, RESET_KEY_PREFIX)
        assert int(fake.get(key)) == 1
        assert 0 < fake.ttl(key) <= 3600

    def test_record_gives_the_daily_counter_an_expiry(self):
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_window_seconds=3600
        )

        throttle.record("user@example.com")

        key = _daily_key(fake, RESET_KEY_PREFIX)
        assert int(fake.get(key)) == 1
        assert 0 < fake.ttl(key) <= 3600

    def test_a_later_send_does_not_extend_the_daily_window(self):
        """The window opens with the first send; a second one must not restart it."""
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_window_seconds=3600
        )
        throttle.record("user@example.com")
        key = _daily_key(fake, RESET_KEY_PREFIX)
        fake.expire(key, 100)

        throttle.record("user@example.com")

        assert int(fake.get(key)) == 2
        assert 0 < fake.ttl(key) <= 100

    def test_allow_heals_a_counter_left_without_an_expiry(self):
        """An older version could leave a count with no TTL, which then refused for good."""
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_cap=5, daily_window_seconds=3600
        )
        throttle.record("user@example.com")
        key = _daily_key(fake, RESET_KEY_PREFIX)
        fake.set(key, 3)
        assert fake.ttl(key) == -1
        fake.delete(*fake.keys("reset:cooldown:*"))

        assert throttle.allow("user@example.com") is True

        assert int(fake.get(key)) == 4
        assert 0 < fake.ttl(key) <= 3600

    def test_record_heals_a_counter_left_without_an_expiry(self):
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_window_seconds=3600
        )
        throttle.record("user@example.com")
        key = _daily_key(fake, RESET_KEY_PREFIX)
        fake.set(key, 3)
        assert fake.ttl(key) == -1

        throttle.record("user@example.com")

        assert int(fake.get(key)) == 4
        assert 0 < fake.ttl(key) <= 3600

    # apply_pipeline=False: the drop comes before EXEC, so no key exists and only the
    # fail-open result is asserted; True: the key exists and must carry a TTL.
    @pytest.mark.parametrize("apply_pipeline", [False, True])
    @pytest.mark.parametrize("method", ["allow", "record"])
    def test_a_drop_during_the_daily_update_never_leaves_a_counter_without_expiry(
        self, method, apply_pipeline
    ):
        """The connection dropping mid-update must not leave a count that never expires.

        Left alone, such a count reaches the cap and refuses the address on every later day.
        The call still fails open: ``allow`` says yes and ``record`` raises nothing.
        """
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            _DroppingClient(fake, apply_pipeline=apply_pipeline),
            key_prefix=RESET_KEY_PREFIX,
            daily_window_seconds=3600,
        )

        result = getattr(throttle, method)("user@example.com")

        assert result is (True if method == "allow" else None)
        for key in fake.keys("reset:daily:*"):
            assert fake.ttl(key) > 0

    @pytest.mark.parametrize("method", ["allow", "record"])
    def test_a_failed_heal_fails_open_and_the_next_send_heals(self, method):
        fake = fakeredis.FakeStrictRedis()
        inner = RedisEmailSendThrottle(fake, key_prefix=RESET_KEY_PREFIX, daily_window_seconds=3600)
        inner.record("user@example.com")
        key = _daily_key(fake, RESET_KEY_PREFIX)
        fake.set(key, 3)
        broken = RedisEmailSendThrottle(
            _ExpireFails(fake), key_prefix=RESET_KEY_PREFIX, daily_window_seconds=3600
        )
        fake.delete(*fake.keys("reset:cooldown:*"))

        result = getattr(broken, method)("user@example.com")

        assert result is (True if method == "allow" else None)
        assert fake.ttl(key) == -1

        fake.delete(*fake.keys("reset:cooldown:*"))
        getattr(inner, method)("user@example.com")

        assert fake.ttl(key) > 0

    def test_allow_heals_a_legacy_counter_stuck_at_the_cap(self):
        """A capped counter with no expiry is the bug's harm: it must get a window."""
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_cap=3, daily_window_seconds=3600
        )
        throttle.record("user@example.com")
        key = _daily_key(fake, RESET_KEY_PREFIX)
        fake.set(key, 3)
        fake.delete(*fake.keys("reset:cooldown:*"))

        assert throttle.allow("user@example.com") is False

        assert int(fake.get(key)) == 3
        assert 0 < fake.ttl(key) <= 3600

    def test_a_failed_heal_of_a_capped_counter_fails_open_and_the_next_allow_heals(self):
        fake = fakeredis.FakeStrictRedis()
        healthy = RedisEmailSendThrottle(
            fake, key_prefix=RESET_KEY_PREFIX, daily_cap=3, daily_window_seconds=3600
        )
        healthy.record("user@example.com")
        key = _daily_key(fake, RESET_KEY_PREFIX)
        fake.set(key, 3)
        broken = RedisEmailSendThrottle(
            _ExpireFails(fake),
            key_prefix=RESET_KEY_PREFIX,
            daily_cap=3,
            daily_window_seconds=3600,
        )
        fake.delete(*fake.keys("reset:cooldown:*"))

        # The store error is swallowed as everywhere else: the send goes ahead.
        assert broken.allow("user@example.com") is True
        assert fake.ttl(key) == -1
        assert int(fake.get(key)) == 3

        fake.delete(*fake.keys("reset:cooldown:*"))
        assert healthy.allow("user@example.com") is False

        assert int(fake.get(key)) == 3
        assert 0 < fake.ttl(key) <= 3600

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
