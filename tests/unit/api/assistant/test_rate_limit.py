"""Tests for the per-user hourly assistant message cap."""

import hashlib
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

    def test_retry_after_is_the_whole_seconds_left_in_the_window(self):
        """
        GIVEN a spent budget whose window opened at t=1000
        WHEN retry_after is asked at t=1600.5
        THEN it is the time left, rounded up to a whole second
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=1000.0):
            throttle.hit(user_id)
            throttle.hit(user_id)

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=1600.5):
            seconds = throttle.retry_after(user_id)

        # THEN
        assert seconds == 3000

    def test_retry_after_is_one_second_for_an_unknown_or_closed_window(self):
        """
        GIVEN one user never seen and one whose window has just closed
        WHEN retry_after is asked for each
        THEN both get the one-second floor, never zero
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            throttle.hit(user_id)

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=3600.0):
            closed = throttle.retry_after(user_id)
        unknown = throttle.retry_after(uuid4())

        # THEN
        assert closed == 1
        assert unknown == 1

    def test_remaining_reports_the_open_window_and_none_otherwise(self):
        """
        GIVEN a user counted at t=0 and another never seen
        WHEN remaining is asked at t=600 and again at t=3600
        THEN it is the seconds left while the window is open, and None for the unknown
             user and once the window has closed
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            throttle.hit(user_id)

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=600.0):
            open_window = throttle.remaining(rate_limit._digest(user_id))
        with patch.object(rate_limit.time, "monotonic", return_value=3600.0):
            closed = throttle.remaining(rate_limit._digest(user_id))
        unknown = throttle.remaining(rate_limit._digest(uuid4()))

        # THEN
        assert open_window == 3000
        assert closed is None
        assert unknown is None

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

    def test_a_fixed_key_is_counted_apart_from_users(self):
        """
        GIVEN a budget of two and a user who has spent both of their messages
        WHEN the global key is hit
        THEN it has a budget of its own, and its refusal reports its own window
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=2, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            throttle.hit(user_id)
            throttle.hit(user_id)

            # WHEN
            outcomes = [throttle.hit_key(rate_limit.GLOBAL_KEY) for _ in range(3)]
        with patch.object(rate_limit.time, "monotonic", return_value=600.0):
            seconds = throttle.retry_after_key(rate_limit.GLOBAL_KEY)
            window = throttle.remaining(rate_limit.GLOBAL_KEY)

        # THEN
        assert outcomes == [True, True, False]
        assert seconds == 3000
        assert window == 3000

    def test_a_user_hit_is_a_hit_under_the_users_digest(self):
        """
        GIVEN a budget of one and a user who has spent it through hit
        WHEN the same digest is hit as a key
        THEN it is refused, so the user methods and the key methods count together
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        user_id = uuid4()
        throttle.hit(user_id)

        # WHEN/THEN
        assert throttle.hit_key(rate_limit._digest(user_id)) is False

    def test_zero_means_no_limit_for_a_key_too(self):
        """
        GIVEN a budget of zero
        WHEN the global key is hit repeatedly
        THEN every hit is allowed
        """
        throttle = InMemoryAssistantThrottle(max_per_hour=0)

        assert [throttle.hit_key(rate_limit.GLOBAL_KEY) for _ in range(5)] == [True] * 5

    def test_a_refund_gives_the_slot_back(self):
        """
        GIVEN a budget of one and a user who spent it
        WHEN the charge is refunded
        THEN the user may send again
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        user_id = uuid4()
        charge = throttle.charge(user_id)
        assert charge.allowed is True

        # WHEN
        throttle.refund(charge)

        # THEN
        assert throttle.hit(user_id) is True

    def test_charges_report_allowed_then_refused_and_name_the_users_digest(self):
        """
        GIVEN a budget of one
        WHEN a user is charged twice
        THEN the charges are allowed and refused, and both name the user's digest
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        user_id = uuid4()

        # WHEN
        first, second = throttle.charge(user_id), throttle.charge(user_id)

        # THEN
        assert (first.allowed, second.allowed) == (True, False)
        assert first.key == second.key == rate_limit._digest(user_id)
        assert first.in_store is False

    def test_a_refund_after_the_window_closed_is_a_no_op_and_creates_no_entry(self):
        """
        GIVEN a charge taken at t=0 in a one-hour window
        WHEN it is refunded at t=3600, once the window has closed
        THEN nothing changes and no entry is created
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1, window_seconds=3600)
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            charge = throttle.charge(uuid4())

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=3600.0):
            throttle.refund(charge)

        # THEN
        assert throttle._counts == {charge.key: (1, 0.0)}

    def test_a_refund_after_the_window_was_replaced_leaves_the_new_window_alone(self):
        """
        GIVEN a charge taken at t=0, then a new window for the same key opened at t=4000
        WHEN the old charge is refunded at t=4001
        THEN the new window keeps its message
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=5, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            old = throttle.charge(user_id)
        with patch.object(rate_limit.time, "monotonic", return_value=4000.0):
            throttle.hit(user_id)

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=4001.0):
            throttle.refund(old)

        # THEN
        assert throttle._counts[old.key] == (1, 4000.0)

    def test_a_refund_never_creates_an_entry(self):
        """
        GIVEN a charge for a key the table has dropped
        WHEN it is refunded
        THEN the table stays empty
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        charge = throttle.charge(uuid4())
        throttle._counts.clear()

        # WHEN
        throttle.refund(charge)

        # THEN
        assert throttle._counts == {}

    def test_a_refund_of_a_refused_charge_is_a_no_op(self):
        """
        GIVEN a budget of one, spent, and a second charge that was refused
        WHEN the refused charge is refunded
        THEN the count is unchanged and the user is still refused
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        user_id = uuid4()
        throttle.charge(user_id)
        refused = throttle.charge(user_id)
        assert refused.allowed is False
        before = dict(throttle._counts)

        # WHEN
        throttle.refund(refused)

        # THEN
        assert throttle._counts == before
        assert throttle.hit(user_id) is False

    def test_a_refund_of_an_uncounted_charge_is_a_no_op(self):
        """
        GIVEN a budget of zero, so a charge stores nothing
        WHEN the charge is refunded
        THEN it is not counted and the table stays empty
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=0)
        charge = throttle.charge(uuid4())

        # WHEN
        throttle.refund(charge)

        # THEN
        assert charge.allowed is True
        assert charge.window_opened is None
        assert charge.in_store is False
        assert throttle._counts == {}

    def test_a_refund_never_takes_the_count_below_zero(self):
        """
        GIVEN a charge refunded once already
        WHEN it is refunded a second time
        THEN the count stays at zero
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=2)
        charge = throttle.charge(uuid4())
        throttle.refund(charge)

        # WHEN
        throttle.refund(charge)

        # THEN
        assert throttle._counts[charge.key][0] == 0

    def test_a_refund_works_for_the_global_key(self):
        """
        GIVEN a budget of one spent under the global key
        WHEN the charge is refunded
        THEN the key may be charged again
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        charge = throttle.charge_key(rate_limit.GLOBAL_KEY)

        # WHEN
        throttle.refund(charge)

        # THEN
        assert throttle.hit_key(rate_limit.GLOBAL_KEY) is True

    def test_a_refused_charge_leaves_the_count_as_it_found_it(self):
        """
        GIVEN a budget of one, spent
        WHEN the user is charged twice more
        THEN both charges are refused and the count is still one
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        user_id = uuid4()
        spent = throttle.charge(user_id)

        # WHEN
        refused = [throttle.charge(user_id), throttle.charge(user_id)]

        # THEN
        assert [c.allowed for c in refused] == [False, False]
        assert throttle._counts[spent.key][0] == 1

    def test_an_overlapping_refusal_does_not_outlive_the_refund_of_the_charge_it_met(self):
        """
        GIVEN a budget of one, a first charge that was allowed and a second that was refused
        WHEN the first charge is refunded
        THEN the count is zero and the next charge is allowed
        """
        # GIVEN
        throttle = InMemoryAssistantThrottle(max_per_hour=1)
        user_id = uuid4()
        first = throttle.charge(user_id)
        assert throttle.charge(user_id).allowed is False

        # WHEN
        throttle.refund(first)

        # THEN
        assert throttle._counts[first.key][0] == 0
        assert throttle.charge(user_id).allowed is True


def _key(fake: fakeredis.FakeStrictRedis) -> bytes:
    """Return the only key the throttle wrote."""
    (key,) = fake.keys("*")
    return key


class TestRedisAssistantThrottle:
    """The Redis throttle shares the cap across processes, or counts per process when it is down."""

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

    def test_retry_after_is_the_remaining_ttl(self):
        """
        GIVEN a spent budget whose key has 100 seconds left
        WHEN retry_after is asked
        THEN it is that TTL
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        throttle.hit(user_id)
        throttle.hit(user_id)
        fake.expire(_key(fake), 100)

        # WHEN
        seconds = throttle.retry_after(user_id)

        # THEN
        assert seconds == 100

    def test_retry_after_is_one_second_when_the_key_has_just_gone(self):
        """
        GIVEN a window that closed between the refusal and the question (TTL -2)
        WHEN retry_after is asked
        THEN it is one second
        """
        throttle = RedisAssistantThrottle(fakeredis.FakeStrictRedis(), max_per_hour=1)

        assert throttle.retry_after(uuid4()) == 1

    def test_retry_after_is_the_full_window_when_the_key_has_no_expiry(self):
        """
        GIVEN a key left without a TTL (-1)
        WHEN retry_after is asked
        THEN it is the full window, the longest the cap can last
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        throttle.hit(user_id)
        fake.persist(_key(fake))

        # WHEN
        seconds = throttle.retry_after(user_id)

        # THEN
        assert seconds == 3600

    def test_retry_after_is_the_full_window_and_logs_without_a_fallback_entry(self, caplog):
        """
        GIVEN a store whose TTL lookup raises a Redis error and a user the process has
            never counted, so there is no fallback entry
        WHEN retry_after is asked
        THEN it is the full window, since one second would understate it, and a record
             names the event without the digest
        """
        # GIVEN
        client = MagicMock()
        client.ttl.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()

        # WHEN
        with caplog.at_level(logging.WARNING, logger="api.security"):
            seconds = throttle.retry_after(user_id)

        # THEN
        assert seconds == 3600
        records = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "assistant_throttle_retry_unavailable"
        ]
        assert len(records) == 1
        assert rate_limit._digest(user_id) not in str(records[0].__dict__)

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

    def test_counts_per_process_and_logs_when_the_store_is_unavailable(self, caplog):
        """
        GIVEN a store whose transaction raises a Redis error and a budget of two
        WHEN one user sends three messages
        THEN the process-local count still refuses the third, and each failed hit writes
             an ERROR record that says the cap is counted per process
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=2)
        user_id = uuid4()

        # WHEN
        with caplog.at_level(logging.ERROR, logger="api.security"):
            outcomes = [throttle.hit(user_id) for _ in range(3)]

        # THEN
        assert outcomes == [True, True, False]
        records = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "assistant_throttle_unavailable"
        ]
        assert len(records) == 3
        assert all(r.levelno == logging.ERROR for r in records)
        assert all("per process" in r.getMessage() for r in records)

    def test_the_fallback_counts_users_apart(self):
        """
        GIVEN a store that is down and a budget of one
        WHEN two users each send two messages, interleaved
        THEN each user's first message is allowed and each user's second is refused
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1)
        first, second = uuid4(), uuid4()

        # WHEN
        outcomes = [
            throttle.hit(first),
            throttle.hit(second),
            throttle.hit(first),
            throttle.hit(second),
        ]

        # THEN
        assert outcomes == [True, True, False, False]

    def test_zero_means_no_limit_even_when_the_store_is_down(self):
        """
        GIVEN a budget of zero and a store that raises on every call
        WHEN one user hits the throttle repeatedly
        THEN every hit is allowed and the store is never touched, because the zero
             limit returns before any call to it
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=0)
        user_id = uuid4()

        # WHEN
        outcomes = [throttle.hit(user_id) for _ in range(5)]

        # THEN
        assert outcomes == [True] * 5
        client.pipeline.assert_not_called()

    def test_retry_after_uses_the_fallback_window_when_the_store_is_down(self):
        """
        GIVEN a store that is down and a user refused by the process-local count
        WHEN 600 seconds into the window the user asks how long to wait
        THEN the answer is the fallback's remaining time, not the full window
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        client.ttl.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            throttle.hit(user_id)
            assert throttle.hit(user_id) is False

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=600.0):
            seconds = throttle.retry_after(user_id)

        # THEN
        assert seconds == 3000

    def test_retry_after_is_the_full_window_once_the_fallback_window_has_closed(self):
        """
        GIVEN a store that is down and a user counted at t=0
        WHEN retry_after is asked at t=7200, past the one-hour window
        THEN the closed fallback entry is ignored and the answer is the full window
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        client.ttl.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            throttle.hit(user_id)

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=7200.0):
            seconds = throttle.retry_after(user_id)

        # THEN
        assert seconds == 3600

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

    def test_the_global_key_is_the_prefix_and_all_and_counts_apart_from_users(self):
        """
        GIVEN a budget of one
        WHEN the global key is hit twice
        THEN the one stored key is assistant:chat:all, the second hit is refused, and a
             user's own counter is untouched
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)

        # WHEN
        outcomes = [throttle.hit_key(rate_limit.GLOBAL_KEY) for _ in range(2)]
        user_id = uuid4()
        user_allowed = throttle.hit(user_id)

        # THEN
        assert outcomes == [True, False]
        assert user_allowed is True
        assert set(fake.keys("*")) == {
            b"assistant:chat:all",
            f"assistant:chat:{rate_limit._digest(user_id)}".encode(),
        }

    def test_retry_after_key_is_the_ttl_of_the_global_key(self):
        """
        GIVEN a spent global counter with 100 seconds left
        WHEN retry_after_key is asked for it
        THEN it is that TTL
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        throttle.hit_key(rate_limit.GLOBAL_KEY)
        throttle.hit_key(rate_limit.GLOBAL_KEY)
        fake.expire(b"assistant:chat:all", 100)

        # WHEN/THEN
        assert throttle.retry_after_key(rate_limit.GLOBAL_KEY) == 100

    def test_the_global_key_is_counted_per_process_when_the_store_is_down(self):
        """
        GIVEN a store that is down, a budget of one and 600 seconds into the window
        WHEN the global key is hit twice and its refusal asks how long to wait
        THEN the second hit is refused by the process-local count, and the wait is the
             fallback's remaining window
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        client.ttl.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1, window_seconds=3600)

        # WHEN
        with patch.object(rate_limit.time, "monotonic", return_value=0.0):
            outcomes = [throttle.hit_key(rate_limit.GLOBAL_KEY) for _ in range(2)]
        with patch.object(rate_limit.time, "monotonic", return_value=600.0):
            seconds = throttle.retry_after_key(rate_limit.GLOBAL_KEY)

        # THEN
        assert outcomes == [True, False]
        assert seconds == 3000

    def test_zero_means_no_limit_for_a_key_and_never_touches_redis(self):
        """
        GIVEN a budget of zero and a client that fails on any call
        WHEN the global key is hit
        THEN it is allowed and the client is never used
        """
        client = MagicMock()
        throttle = RedisAssistantThrottle(client, max_per_hour=0)

        assert throttle.hit_key(rate_limit.GLOBAL_KEY) is True
        assert client.mock_calls == []

    def test_a_refund_gives_the_slot_back_and_keeps_the_ttl(self):
        """
        GIVEN a budget of one, spent, on a key whose TTL has been shortened to 100 seconds
        WHEN the charge is refunded
        THEN the user may send again and the TTL was not touched
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        charge = throttle.charge(user_id)
        key = _key(fake)
        fake.expire(key, 100)

        # WHEN
        throttle.refund(charge)

        # THEN
        assert charge.in_store is True
        assert int(fake.get(key)) == 0
        assert 0 < fake.ttl(key) <= 100
        assert throttle.hit(user_id) is True

    def test_a_refund_on_an_expired_key_creates_no_key(self):
        """
        GIVEN a charge whose key has expired
        WHEN the charge is refunded
        THEN no key exists, so the next window starts clean instead of at -1 with no TTL
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)
        charge = throttle.charge(uuid4())
        fake.delete(_key(fake))

        # WHEN
        throttle.refund(charge)

        # THEN
        assert fake.keys("*") == []

    def test_a_refund_after_the_window_rolled_over_takes_one_off_the_new_window(self):
        """
        GIVEN a charge whose key expired and a second charge that opened a new window
        WHEN the first charge is refunded
        THEN the new window drops to zero and keeps its TTL: the accepted trade-off
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=2, window_seconds=3600)
        user_id = uuid4()
        first = throttle.charge(user_id)
        key = _key(fake)
        assert int(fake.get(key)) == 1
        fake.delete(key)
        throttle.charge(user_id)
        assert int(fake.get(key)) == 1

        # WHEN
        throttle.refund(first)

        # THEN
        assert int(fake.get(key)) == 0
        assert fake.ttl(key) > 0

    def test_a_refund_on_a_key_at_zero_leaves_it_at_zero(self):
        """
        GIVEN a key at zero
        WHEN the charge is refunded
        THEN the key stays at zero with its TTL
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=2, window_seconds=3600)
        charge = throttle.charge(uuid4())
        key = _key(fake)
        throttle.refund(charge)

        # WHEN
        throttle.refund(charge)

        # THEN
        assert int(fake.get(key)) == 0
        assert 0 < fake.ttl(key) <= 3600

    def test_a_refund_of_a_refused_or_uncounted_charge_is_a_no_op(self):
        """
        GIVEN a spent key with a refused charge, and a zero-budget throttle with a client
              that records every call
        WHEN each charge is refunded
        THEN the key still holds its count and the zero-budget client is never used
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)
        user_id = uuid4()
        throttle.charge(user_id)
        refused = throttle.charge(user_id)
        client = MagicMock()
        off = RedisAssistantThrottle(client, max_per_hour=0)
        uncounted = off.charge(uuid4())

        # WHEN
        throttle.refund(refused)
        off.refund(uncounted)

        # THEN
        assert refused.allowed is False
        assert int(fake.get(_key(fake))) == 1
        assert client.mock_calls == []

    def test_a_charge_taken_by_the_fallback_is_refunded_to_the_fallback(self):
        """
        GIVEN a store that is down for the charge and up again for the refund
        WHEN the fallback's charge is refunded
        THEN the fallback's count drops, and the store is not asked
        """
        # GIVEN
        client = MagicMock()
        client.pipeline.return_value.execute.side_effect = redis.RedisError("down")
        throttle = RedisAssistantThrottle(client, max_per_hour=1)
        user_id = uuid4()
        charge = throttle.charge(user_id)
        assert charge.in_store is False

        # WHEN
        throttle.refund(charge)

        # THEN
        client.eval.assert_not_called()
        assert throttle._fallback.hit(user_id) is True

    def test_a_store_error_during_a_refund_is_logged_and_not_raised(self, caplog):
        """
        GIVEN a charge Redis took and a store that now raises on the refund
        WHEN the charge is refunded
        THEN nothing is raised, a WARNING record names the event without the key or digest,
             and the fallback is not touched
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)
        user_id = uuid4()
        charge = throttle.charge(user_id)
        client = MagicMock()
        client.eval.side_effect = redis.RedisError("down")
        throttle._client = client

        # WHEN
        with caplog.at_level(logging.WARNING, logger="api.security"):
            throttle.refund(charge)

        # THEN
        records = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "assistant_throttle_refund_unavailable"
        ]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert records[0].exc_info is not None
        assert rate_limit._digest(user_id) not in str(records[0].__dict__)
        assert throttle._fallback._counts == {}

    def test_a_refund_works_for_the_global_key(self):
        """
        GIVEN a budget of one spent under the global key
        WHEN the charge is refunded
        THEN the key may be charged again
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)
        charge = throttle.charge_key(rate_limit.GLOBAL_KEY)

        # WHEN
        throttle.refund(charge)

        # THEN
        assert charge.key == rate_limit.GLOBAL_KEY
        assert throttle.hit_key(rate_limit.GLOBAL_KEY) is True

    def test_a_refused_charge_leaves_the_count_and_the_ttl_as_it_found_them(self):
        """
        GIVEN a budget of one, spent, on a key whose TTL has been shortened to 100 seconds
        WHEN the user is charged twice more
        THEN both charges are refused, the count is still one and the TTL was not touched
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        throttle.charge(user_id)
        key = _key(fake)
        fake.expire(key, 100)

        # WHEN
        refused = [throttle.charge(user_id), throttle.charge(user_id)]

        # THEN
        assert [c.allowed for c in refused] == [False, False]
        assert int(fake.get(key)) == 1
        assert 0 < fake.ttl(key) <= 100

    def test_an_overlapping_refusal_does_not_outlive_the_refund_of_the_charge_it_met(self):
        """
        GIVEN a budget of one, a first charge that was allowed and a second that was refused
        WHEN the first charge is refunded
        THEN the count is zero and the next charge is allowed
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        first = throttle.charge(user_id)
        assert throttle.charge(user_id).allowed is False

        # WHEN
        throttle.refund(first)

        # THEN
        assert int(fake.get(_key(fake))) == 0
        assert throttle.charge(user_id).allowed is True

    def test_a_refused_charge_on_a_key_that_just_expired_creates_no_key(self):
        """
        GIVEN a charge over budget whose key expires between the INCR and the give-back
        WHEN the give-back runs
        THEN the guarded script leaves no key behind, so no counter without a TTL is created
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1, window_seconds=3600)
        user_id = uuid4()
        throttle.charge(user_id)
        key = _key(fake)
        real_eval = fake.eval

        def expire_then_eval(*args, **kwargs):
            fake.delete(key)
            return real_eval(*args, **kwargs)

        # WHEN
        with patch.object(fake, "eval", side_effect=expire_then_eval):
            refused = throttle.charge(user_id)

        # THEN
        assert refused.allowed is False
        assert fake.keys("*") == []

    def test_a_store_error_while_giving_back_a_refused_charge_is_logged_and_not_raised(
        self, caplog
    ):
        """
        GIVEN a spent budget and a store that raises on the give-back of the refused increment
        WHEN the user is charged again
        THEN the charge is refused, nothing is raised, and a WARNING record names the event
             without the key or digest
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)
        user_id = uuid4()
        throttle.charge(user_id)

        # WHEN
        with (
            patch.object(fake, "eval", side_effect=redis.RedisError("down")),
            caplog.at_level(logging.WARNING, logger="api.security"),
        ):
            refused = throttle.charge(user_id)

        # THEN
        records = [
            r
            for r in caplog.records
            if getattr(r, "event", None) == "assistant_throttle_giveback_unavailable"
        ]
        assert refused.allowed is False
        assert refused.in_store is True
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert records[0].exc_info is not None
        assert rate_limit._digest(user_id) not in str(records[0].__dict__)
        assert throttle._fallback._counts == {}

    def test_close_closes_the_redis_client(self):
        """
        GIVEN a Redis-backed throttle
        WHEN it is closed
        THEN its client is closed
        """
        # GIVEN
        client = MagicMock()
        throttle = RedisAssistantThrottle(client, max_per_hour=1)

        # WHEN
        throttle.close()

        # THEN
        client.close.assert_called_once_with()


class TestGetAssistantThrottle:
    """The factory selects the Redis backend only when configured."""

    @pytest.fixture(autouse=True)
    def _fresh_cache(self):
        """Keep the process-wide caches from leaking between tests."""
        rate_limit.get_assistant_throttle.cache_clear()
        rate_limit.get_assistant_global_throttle.cache_clear()
        rate_limit.get_assistant_address_throttle.cache_clear()
        yield
        rate_limit.get_assistant_throttle.cache_clear()
        rate_limit.get_assistant_global_throttle.cache_clear()
        rate_limit.get_assistant_address_throttle.cache_clear()

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

    def test_the_global_throttle_takes_its_own_budget_and_backend(self):
        """
        GIVEN per-user and global budgets that differ, with and without a redis_url
        WHEN the global throttle is built
        THEN it carries the global budget, on Redis when configured and in memory otherwise
        """
        # GIVEN
        with_redis = SimpleNamespace(
            redis_url="redis://cache:6379/0",
            assistant_rate_limit_per_hour=60,
            assistant_global_turns_per_hour=7,
        )
        without = SimpleNamespace(
            redis_url="", assistant_rate_limit_per_hour=60, assistant_global_turns_per_hour=7
        )

        # WHEN
        with (
            patch.object(rate_limit, "get_settings", return_value=with_redis),
            patch.object(rate_limit.redis, "from_url", return_value=MagicMock()),
        ):
            hosted = rate_limit.get_assistant_global_throttle()
        rate_limit.get_assistant_global_throttle.cache_clear()
        with patch.object(rate_limit, "get_settings", return_value=without):
            local = rate_limit.get_assistant_global_throttle()
            again = rate_limit.get_assistant_global_throttle()

        # THEN
        assert isinstance(hosted, RedisAssistantThrottle)
        assert hosted._max == 7
        assert isinstance(local, InMemoryAssistantThrottle)
        assert local._max == 7
        assert again is local

    def test_the_address_throttle_takes_its_own_budget_and_backend(self):
        """
        GIVEN per-user, global and per-address budgets that differ, with and without a redis_url
        WHEN the address throttle is built
        THEN it carries the address budget, on Redis when configured and in memory otherwise
        """
        # GIVEN
        fields = {
            "assistant_rate_limit_per_hour": 60,
            "assistant_global_turns_per_hour": 600,
            "assistant_address_turns_per_hour": 9,
        }
        with_redis = SimpleNamespace(redis_url="redis://cache:6379/0", **fields)
        without = SimpleNamespace(redis_url="", **fields)

        # WHEN
        with (
            patch.object(rate_limit, "get_settings", return_value=with_redis),
            patch.object(rate_limit.redis, "from_url", return_value=MagicMock()),
        ):
            hosted = rate_limit.get_assistant_address_throttle()
        rate_limit.get_assistant_address_throttle.cache_clear()
        with patch.object(rate_limit, "get_settings", return_value=without):
            local = rate_limit.get_assistant_address_throttle()
            again = rate_limit.get_assistant_address_throttle()

        # THEN
        assert isinstance(hosted, RedisAssistantThrottle)
        assert hosted._max == 9
        assert isinstance(local, InMemoryAssistantThrottle)
        assert local._max == 9
        assert again is local


def _keyed(log_hash_key: str | None = None, secret_key: str | None = None):
    """Patch the module's settings with the two keys ``address_key`` may use."""
    settings = SimpleNamespace(log_hash_key=log_hash_key, secret_key=secret_key or "secret-a")
    return patch.object(rate_limit, "get_settings", return_value=settings)


class TestAddressKey:
    """A client address is counted under a keyed hash of its network, never under the address."""

    def test_one_ipv4_address_always_maps_to_the_same_key_and_two_addresses_differ(self):
        """
        GIVEN two IPv4 addresses
        WHEN each is keyed twice
        THEN an address keeps its key, and the two keys differ
        """
        # WHEN
        with _keyed():
            first = rate_limit.address_key("203.0.113.5")
            again = rate_limit.address_key("203.0.113.5")
            other = rate_limit.address_key("203.0.113.6")

        # THEN
        assert first == again
        assert first != other

    def test_addresses_of_one_ipv6_network_share_a_key_and_other_networks_do_not(self):
        """
        GIVEN IPv6 addresses inside one /64, and one in the next /64
        WHEN they are keyed
        THEN the first two share a key, spelled out in full or compressed, and the third differs
        """
        # WHEN
        with _keyed():
            one = rate_limit.address_key("2001:db8:1:2::1")
            same_network = rate_limit.address_key("2001:0db8:0001:0002:ffff:ffff:ffff:ffff")
            next_network = rate_limit.address_key("2001:db8:1:3::1")

        # THEN
        assert one == same_network
        assert one != next_network

    def test_an_ipv4_mapped_ipv6_address_counts_as_its_ipv4_address(self):
        """
        GIVEN an IPv4 address and the same address written as IPv4-mapped IPv6
        WHEN both are keyed
        THEN the keys are equal, and a different mapped address differs
        """
        # WHEN
        with _keyed():
            plain = rate_limit.address_key("203.0.113.5")
            mapped = rate_limit.address_key("::ffff:203.0.113.5")
            other = rate_limit.address_key("::ffff:203.0.113.6")

        # THEN
        assert plain == mapped
        assert plain != other

    @pytest.mark.parametrize("value", ["unverified-origin", "unknown", "not an address"])
    def test_a_value_that_is_not_an_address_is_keyed_as_it_is(self, value):
        """
        GIVEN a value get_client_ip may return that is not an address
        WHEN it is keyed
        THEN the key is stable, differs from an address key, and shows no part of the value
        """
        # WHEN
        with _keyed():
            key = rate_limit.address_key(value)
            again = rate_limit.address_key(value)

        # THEN
        assert key == again
        assert key != rate_limit.address_key("203.0.113.5")
        assert key.startswith(rate_limit.ADDRESS_KEY_PREFIX)
        assert value not in key

    def test_the_key_is_an_hmac_and_not_a_plain_digest_of_the_address(self):
        """
        GIVEN an IPv4 address
        WHEN it is keyed
        THEN the key is neither the address, nor its SHA-256 digest, nor the digest under the
            domain prefix alone, since an unkeyed hash of the small IPv4 space could be reversed
        """
        # WHEN
        with _keyed():
            key = rate_limit.address_key("203.0.113.5")

        # THEN
        digest = key.removeprefix(rate_limit.ADDRESS_KEY_PREFIX)
        assert len(digest) == 64
        assert "203.0.113.5" not in key
        assert digest != hashlib.sha256(b"203.0.113.5").hexdigest()
        assert digest != hashlib.sha256(b"assistant-address:203.0.113.5").hexdigest()

    def test_the_key_follows_the_log_hash_key_and_falls_back_to_the_secret_key(self):
        """
        GIVEN one address, a secret key and a separate log hash key
        WHEN it is keyed under each combination
        THEN the log hash key decides when it is set, the secret key otherwise, and changing
            the deciding key changes the result
        """
        # WHEN
        with _keyed(log_hash_key=None, secret_key="secret-a"):  # pragma: allowlist secret
            by_secret = rate_limit.address_key("203.0.113.5")
        with _keyed(log_hash_key=None, secret_key="secret-b"):  # pragma: allowlist secret
            other_secret = rate_limit.address_key("203.0.113.5")
        with _keyed(log_hash_key="log-key", secret_key="secret-a"):
            by_log_key = rate_limit.address_key("203.0.113.5")
        with _keyed(log_hash_key="log-key", secret_key="secret-b"):
            log_key_alone = rate_limit.address_key("203.0.113.5")

        # THEN
        assert by_secret != other_secret
        assert by_log_key == log_key_alone
        assert by_log_key != by_secret

    def test_the_key_equals_no_user_digest_and_not_the_global_key(self):
        """
        GIVEN a keyed address and the key forms of a user and of the global ceiling
        WHEN the Redis keys are compared
        THEN the address's differs from both, so the three counters never share a key
        """
        # WHEN
        with _keyed():
            key = rate_limit.address_key("203.0.113.5")

        # THEN
        assert key != rate_limit.GLOBAL_KEY
        assert key != rate_limit._digest(uuid4())
        assert ":" in key
        assert ":" not in rate_limit._digest(uuid4())

    def test_a_redis_counter_for_an_address_lives_under_its_own_key(self):
        """
        GIVEN a Redis-backed throttle with a cap of one
        WHEN an address is charged twice
        THEN the second charge is refused and the store holds one key, under the address
            prefix, with an hour-long expiry
        """
        # GIVEN
        fake = fakeredis.FakeStrictRedis()
        throttle = RedisAssistantThrottle(fake, max_per_hour=1)
        with _keyed():
            key = rate_limit.address_key("203.0.113.5")

        # WHEN
        first = throttle.charge_key(key)
        second = throttle.charge_key(key)

        # THEN
        assert (first.allowed, second.allowed) == (True, False)
        (stored,) = fake.keys("*")
        assert stored.decode() == f"{rate_limit.KEY_PREFIX}:{key}"
        assert 0 < fake.ttl(stored) <= rate_limit.WINDOW_SECONDS
