"""Tests for the per-user hourly assistant message cap."""

import logging
import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import fakeredis
import pytest
import redis

from api.assistant import rate_limit
from api.assistant.rate_limit import (
    AssistantThrottle,
    InMemoryAssistantThrottle,
    RedisAssistantThrottle,
)


class TestInMemoryAssistantThrottle:
    """The in-memory throttle caps messages per user within a fixed window."""

    def test_allows_up_to_the_limit_then_blocks(self):
        """
        GIVEN a budget of two messages
        WHEN one user sends three
        THEN the third is refused
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=2)
        user_id = uuid4()

        # WHEN
        outcomes = [throttle.hit(user_id) for _ in range(3)]

        # THEN
        assert outcomes == [True, True, False]

    def test_tracks_users_independently(self):
        """
        GIVEN a budget of one message
        WHEN two different users each send one
        THEN both are allowed
        """
        throttle = InMemoryAssistantThrottle(max_per_hour=1)

        assert throttle.hit(uuid4()) is True
        assert throttle.hit(uuid4()) is True

    def test_a_new_window_starts_after_the_old_one_expires(self):
        """
        GIVEN a spent budget
        WHEN the window length has passed
        THEN the user may send again
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=1000.0):
            assert throttle.hit(user_id) is True
            assert throttle.hit(user_id) is False

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=1000.0 + 3600):
            allowed = throttle.hit(user_id)

        # THEN
        assert allowed is True

    def test_the_window_is_fixed_and_not_pushed_back_by_later_messages(self):
        """
        GIVEN a message at t=0 and a refused one at t=3000
        WHEN the user sends at t=3601
        THEN the window opened at t=0 has ended, so the message is allowed
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            throttle.hit(user_id)
        with patch.object(rate_limit.time, "monotonic", return_value=3000.0):
            assert throttle.hit(user_id) is False

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=3601.0):
            allowed = throttle.hit(user_id)

        # THEN
        assert allowed is True

    def test_expired_windows_are_dropped(self):
        """
        GIVEN many users whose windows have all expired
        WHEN any user sends the next message
        THEN the stale entries are cleaned out of the table
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=5, window_seconds=60)
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            for _ in range(50):
                throttle.hit(uuid4())

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=120.0):
            throttle.hit(uuid4())

        # THEN
        assert len(throttle._counts) == 1

    def test_zero_means_no_limit(self):
        """
        GIVEN a budget of zero
        WHEN a user sends many messages
        THEN every one is allowed
        """
        throttle = InMemoryAssistantThrottle(max_per_hour=0)
        user_id = uuid4()

        assert all(throttle.hit(user_id) for _ in range(100))

    def test_concurrent_hits_never_exceed_the_budget(self):
        """
        GIVEN a budget of 1000 and 8 threads sending 200 messages each, with the
              interpreter switching threads as often as it can
        WHEN they all hit at once
        THEN exactly 1000 are allowed, so no increment was lost to a race

        The switch interval is lowered because at the default 5 ms a thread finishes its
        whole loop before it is preempted, and a lock-free table passes anyway.
        """
        # GIVEN
        threads_count, hits_each, budget = 8, 200, 1000
        throttle = InMemoryAssistantThrottle(max_per_hour=budget)
        user_id = uuid4()
        start = threading.Barrier(threads_count)
        results: list[list[bool]] = [[] for _ in range(threads_count)]

        def worker(index: int) -> None:
            start.wait()
            results[index] = [throttle.hit(user_id) for _ in range(hits_each)]

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(threads_count)]
        previous_interval = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)

        # WHEN
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        finally:
            sys.setswitchinterval(previous_interval)

        # THEN
        allowed = [outcome for chunk in results for outcome in chunk]
        assert len(allowed) == threads_count * hits_each
        assert allowed.count(True) == budget


def _key(fake: fakeredis.FakeStrictRedis) -> bytes:
    """Return the only key the throttle wrote."""
    (key,) = fake.keys("*")
    return key


class TestRedisAssistantThrottle:
    """The Redis throttle shares the cap across processes and fails open."""

    def test_allows_up_to_the_limit_then_blocks(self):
        """
        GIVEN a budget of two messages
        WHEN one user sends three
        THEN the third is refused
        """
        # GIVEN
        throttle = RedisAssistantThrottle(fakeredis.FakeStrictRedis(), max_per_hour=2)
        user_id = uuid4()

        # WHEN
        outcomes = [throttle.hit(user_id) for _ in range(3)]

        # THEN
        assert outcomes == [True, True, False]

    def test_a_key_always_carries_a_ttl(self):
        """
        GIVEN a throttle with a one-hour window
        WHEN a user hits it once
        THEN the key exists with a TTL, so it can never outlive its window
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=5, window_seconds=3600)

        # WHEN
        throttle.hit(uuid4())

        # THEN
        assert 0 < fake.ttl(_key(fake)) <= 3600

    def test_later_hits_do_not_refresh_the_ttl(self):
        """
        GIVEN a key whose TTL has been shortened to 100 seconds
        WHEN the user hits again
        THEN the TTL is not pushed back to the full window
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=5, window_seconds=3600)
        user_id = uuid4()
        throttle.hit(user_id)
        key = _key(fake)
        fake.expire(key, 100)

        # WHEN
        throttle.hit(user_id)

        # THEN
        assert 0 < fake.ttl(key) <= 100

    def test_a_hit_is_one_transaction(self):
        """
        GIVEN a client that records how its pipeline is built
        WHEN a user hits the throttle
        THEN the SET NX and the INCR run in one transactional pipeline
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.return_value = [True, 1]
        throttle = RedisAssistantThrottle(client, max_per_hour=5, window_seconds=3600)

        # WHEN
        allowed = throttle.hit(uuid4())

        # THEN
        assert allowed is True
        client.pipeline.assert_called_once_with(transaction=True)
        pipe = client.pipeline.return_value
        assert pipe.set.call_args.args[1] == 0
        assert pipe.set.call_args.kwargs == {"ex": 3600, "nx": True}
        pipe.incr.assert_called_once_with(pipe.set.call_args.args[0])

    def test_the_key_never_contains_the_raw_user_id(self):
        """
        GIVEN a user id
        WHEN the user hits the throttle
        THEN the stored key holds a digest, not the id
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=5)
        user_id = uuid4()

        # WHEN
        throttle.hit(user_id)

        # THEN
        key = _key(fake).decode()
        assert key.startswith("assistant:chat:")
        assert str(user_id) not in key
        assert user_id.hex not in key

    def test_users_have_separate_counters(self):
        """
        GIVEN a budget of one message
        WHEN two users each send one
        THEN both are allowed
        """
        throttle = RedisAssistantThrottle(fakeredis.FakeStrictRedis(), max_per_hour=1)

        assert throttle.hit(uuid4()) is True
        assert throttle.hit(uuid4()) is True

    def test_zero_means_no_limit_and_never_touches_redis(self):
        """
        GIVEN a budget of zero and a client that fails on any call
        WHEN a user hits the throttle repeatedly
        THEN every hit is allowed and the client is never used
        """
        # GIVEN
        client = MagicMock()
        throttle = RedisAssistantThrottle(client, max_per_hour=0)

        # WHEN
        outcomes = [throttle.hit(uuid4()) for _ in range(5)]

        # THEN
        assert outcomes == [True] * 5
        assert client.mock_calls == []

    def test_fails_open_and_logs_when_the_store_is_unavailable(self, caplog):
        """
        GIVEN a store whose transaction raises a Redis error
        WHEN a user hits the throttle
        THEN the message is allowed and an ERROR record names the event
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1)
        user_id = uuid4()

        # WHEN
        with caplog.at_level(logging.ERROR, logger="api.security"):
            allowed = throttle.hit(user_id)

        # THEN
        assert allowed is True
        records = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "assistant_throttle_unavailable"
        ]
        assert len(records) == 1
        assert records[0].levelno == logging.ERROR

    def test_the_failure_record_never_carries_the_user_or_its_digest(self, caplog):
        """
        GIVEN a store failure while a user hits the throttle
        WHEN the record is written
        THEN neither the user id nor the key digest appears in it
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1)
        user_id = uuid4()
        digest = rate_limit._digest(user_id)

        # WHEN
        with caplog.at_level(logging.ERROR, logger="api.security"):
            throttle.hit(user_id)

        # THEN
        for record in caplog.records:
            assert str(user_id) not in str(record.__dict__)
            assert digest not in str(record.__dict__)
            assert digest not in record.getMessage()


class TestGetAssistantThrottle:
    """The factory selects the Redis backend only when configured."""

    @pytest.fixture(autouse=True)
    def _fresh_cache(self):
        """Keep the process-wide cache from leaking between tests."""
        rate_limit.get_assistant_throttle.cache_clear()
        yield
        rate_limit.get_assistant_throttle.cache_clear()

    def test_uses_redis_when_configured(self):
        """
        GIVEN a configured redis_url
        WHEN the throttle is built
        THEN it is Redis-backed and satisfies the protocol
        """
        # GIVEN
        settings = SimpleNamespace(
            redis_url="redis://cache:6379/0", assistant_rate_limit_per_hour=60
        )
        with (
            patch.object(rate_limit, "get_settings", return_value=settings),
            patch.object(rate_limit.redis, "from_url", return_value=MagicMock()) as from_url,
        ):
            # WHEN
            throttle = rate_limit.get_assistant_throttle()

        # THEN
        assert isinstance(throttle, RedisAssistantThrottle)
        assert isinstance(throttle, AssistantThrottle)
        from_url.assert_called_once()

    def test_falls_back_to_in_memory_without_redis(self):
        """
        GIVEN no redis_url
        WHEN the throttle is built
        THEN it is the in-memory backend
        """
        # GIVEN
        settings = SimpleNamespace(redis_url="", assistant_rate_limit_per_hour=60)

        # WHEN
        with patch.object(rate_limit, "get_settings", return_value=settings):
            throttle = rate_limit.get_assistant_throttle()

        # THEN
        assert isinstance(throttle, InMemoryAssistantThrottle)
