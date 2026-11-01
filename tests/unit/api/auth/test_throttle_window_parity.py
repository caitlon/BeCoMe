"""The in-memory throttles keep the same windows as their Redis twins.

Each scenario runs against both backends of a throttle with one controlled clock, so a
drift in either fails here. The Redis side takes its time from fakeredis' socket module, the
in-memory side from the throttle module's ``datetime``; the fixture points both at one clock.
Scenarios stay clear of the exact instant a window ends, where Redis (key kept until the
clock passes expiry) and the in-memory backends (state dropped at it) differ by one instant.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import fakeredis
import pytest

from api.auth import email_throttle, login_throttle
from api.auth.email_throttle import InMemoryEmailSendThrottle, RedisEmailSendThrottle
from api.auth.login_throttle import (
    MAX_FAILURES,
    WINDOW_SECONDS,
    InMemoryLoginThrottle,
    RedisLoginThrottle,
)

ADDRESS = "user@example.com"
MINUTE = 60
HOUR = 60 * MINUTE


class Clock:
    """A settable clock shared by both backends of a scenario."""

    def __init__(self) -> None:
        self.seconds = datetime(2026, 1, 1, tzinfo=UTC).timestamp()

    def advance(self, seconds: float) -> None:
        self.seconds += seconds

    def now(self, tz=None) -> datetime:
        return datetime.fromtimestamp(self.seconds, UTC)

    def time(self) -> float:
        return self.seconds


@pytest.fixture
def clock():
    """Drive both throttle modules and fakeredis from one clock."""
    controlled = Clock()
    fake_datetime = SimpleNamespace(now=controlled.now)
    with (
        patch.object(login_throttle, "datetime", fake_datetime),
        patch.object(email_throttle, "datetime", fake_datetime),
        patch("fakeredis._socket._base.time", SimpleNamespace(time=controlled.time)),
    ):
        yield controlled


def _redis() -> fakeredis.FakeStrictRedis:
    """Return a client on a server of its own, so no scenario sees another's keys."""
    return fakeredis.FakeStrictRedis(server=fakeredis.FakeServer())


@pytest.fixture(params=["memory", "redis"])
def login(request, clock):
    """A login throttle with the production limits, on each backend."""
    if request.param == "memory":
        return InMemoryLoginThrottle()
    return RedisLoginThrottle(_redis(), key_prefix="login")


class _Stored:
    """Read what a login throttle holds for ``ADDRESS``, whichever backend it is."""

    def __init__(self, throttle, clock: Clock) -> None:
        self._throttle = throttle
        self._clock = clock

    def count(self) -> int | None:
        """Return the stored attempt count, or None when nothing is stored."""
        if isinstance(self._throttle, InMemoryLoginThrottle):
            entry = self._throttle._failures.get(login_throttle._digest(ADDRESS))
            return entry[0] if entry else None
        client = self._throttle._client
        raw = client.get(self._throttle._key(ADDRESS))
        return None if raw is None else int(raw)

    def seconds_left(self) -> float | None:
        """Return the time before the stored count expires, or None when nothing is stored."""
        if isinstance(self._throttle, InMemoryLoginThrottle):
            entry = self._throttle._failures.get(login_throttle._digest(ADDRESS))
            if entry is None:
                return None
            return WINDOW_SECONDS - (self._clock.now() - entry[1]).total_seconds()
        ttl = self._throttle._client.ttl(self._throttle._key(ADDRESS))
        return None if ttl < 0 else float(ttl)


@pytest.fixture
def stored(login, clock) -> _Stored:
    """The raw count and remaining window behind the ``login`` throttle."""
    return _Stored(login, clock)


@pytest.fixture(params=["memory", "redis"])
def email(request, clock):
    """An email-send throttle with the production limits, on each backend."""
    if request.param == "memory":
        return InMemoryEmailSendThrottle()
    return RedisEmailSendThrottle(_redis(), key_prefix="reset")


def _fail(throttle, clock, times: int, gap: float = 1) -> None:
    """Record failures, ``gap`` seconds apart."""
    for index in range(times):
        if index:
            clock.advance(gap)
        throttle.record_failure(ADDRESS)


def _attempt(throttle, clock, gap: float = 0) -> bool:
    """Advance ``gap`` seconds, reserve a slot and, when granted, report it as a failure."""
    clock.advance(gap)
    granted = throttle.reserve(ADDRESS)
    if granted:
        throttle.confirm_failure(ADDRESS)
    return granted


def _send(throttle, clock, gap: float) -> bool:
    """Advance the clock by ``gap`` seconds, then ask for a send."""
    clock.advance(gap)
    return throttle.allow(ADDRESS)


def _fill_the_day(email, clock) -> None:
    """Send five emails 5h45m apart, so the fifth goes out 23 hours after the first."""
    assert email.allow(ADDRESS) is True
    for _ in range(4):
        assert _send(email, clock, 5 * HOUR + 45 * MINUTE) is True


class TestLoginWindow:
    """A lock lasts until the window passes with no new failure."""

    def test_slow_failures_keep_counting(self, login, clock):
        """
        GIVEN failures each 14 minutes after the last, so the first is over an hour old
        WHEN the tenth arrives
        THEN the account is locked, because every failure restarted the window
        """
        _fail(login, clock, times=9, gap=14 * MINUTE)
        assert login.is_locked(ADDRESS) is False

        clock.advance(14 * MINUTE)
        login.record_failure(ADDRESS)

        assert login.is_locked(ADDRESS) is True

    def test_lock_ends_after_a_quiet_window(self, login, clock):
        """
        GIVEN a locked account
        WHEN 15 minutes pass with no failure
        THEN it unlocks, and not before
        """
        _fail(login, clock, times=10)

        clock.advance(14 * MINUTE)
        assert login.is_locked(ADDRESS) is True
        clock.advance(2 * MINUTE)
        assert login.is_locked(ADDRESS) is False

    def test_a_failure_while_locked_extends_the_lock(self, login, clock):
        """
        GIVEN a locked account that fails again 10 minutes into the lock
        WHEN time passes after that failure
        THEN it is still locked at 14 minutes and open at 16
        """
        _fail(login, clock, times=10)
        clock.advance(10 * MINUTE)
        login.record_failure(ADDRESS)

        clock.advance(14 * MINUTE)
        assert login.is_locked(ADDRESS) is True
        clock.advance(2 * MINUTE)
        assert login.is_locked(ADDRESS) is False

    def test_a_stale_count_starts_over(self, login, clock):
        """
        GIVEN five failures followed by a quiet window
        WHEN nine more arrive
        THEN the account is not locked, since the old five no longer count
        """
        _fail(login, clock, times=5)
        clock.advance(16 * MINUTE)

        _fail(login, clock, times=9)

        assert login.is_locked(ADDRESS) is False


class TestLoginReservation:
    """An attempt takes a slot before the password is checked, so a burst cannot overshoot."""

    @pytest.mark.parametrize("round_", range(3))
    def test_parallel_reservations_admit_exactly_the_budget(self, login, stored, round_):
        """
        GIVEN three times as many callers as the budget, released together
        WHEN each reserves a slot
        THEN exactly the budget is granted and the count left is exactly the budget
        """
        callers = 3 * MAX_FAILURES
        start = threading.Barrier(callers, timeout=10)

        def reserve() -> bool:
            start.wait()
            return login.reserve(ADDRESS)

        with ThreadPoolExecutor(max_workers=callers) as pool:
            granted = [future.result() for future in [pool.submit(reserve) for _ in range(callers)]]

        assert granted.count(True) == MAX_FAILURES
        assert stored.count() == MAX_FAILURES

    def test_the_eleventh_reservation_is_refused_and_a_reset_reopens(self, login, clock):
        """
        GIVEN ten reservations, each confirmed as a failure
        WHEN an eleventh is asked for
        THEN it is refused, and after a reset a reservation is granted again
        """
        assert [_attempt(login, clock, gap=1) for _ in range(MAX_FAILURES)] == [True] * MAX_FAILURES

        assert login.reserve(ADDRESS) is False

        login.reset(ADDRESS)
        assert login.reserve(ADDRESS) is True

    def test_a_refused_reservation_does_not_extend_the_window(self, login, stored, clock):
        """
        GIVEN a locked account and a caller who retries every minute for 14 minutes
        WHEN the last real failure is 16 minutes old
        THEN a reservation is granted, and the stored window ran down as if nobody retried
        """
        for _ in range(MAX_FAILURES):
            _attempt(login, clock, gap=1)
        left = stored.seconds_left()
        count = stored.count()

        refusals = [_attempt(login, clock, gap=MINUTE) for _ in range(14)]

        assert refusals == [False] * 14
        assert stored.count() == count
        assert stored.seconds_left() == pytest.approx(left - 14 * MINUTE, abs=1)
        clock.advance(2 * MINUTE)
        assert login.reserve(ADDRESS) is True

    def test_sequential_slow_failures_keep_counting(self, login, clock):
        """
        GIVEN attempts each 14 minutes after the last, so the first is over an hour old
        WHEN the tenth is confirmed
        THEN the account is locked and the next reservation is refused
        """
        assert all(_attempt(login, clock, gap=14 * MINUTE) for _ in range(MAX_FAILURES))

        assert login.is_locked(ADDRESS) is True
        assert login.reserve(ADDRESS) is False

    def test_the_lock_ends_after_a_quiet_window(self, login, clock):
        """
        GIVEN a locked account
        WHEN 14 minutes pass, then two more
        THEN reservations are refused at 14 and granted at 16
        """
        for _ in range(MAX_FAILURES):
            _attempt(login, clock, gap=1)

        clock.advance(14 * MINUTE)
        assert login.reserve(ADDRESS) is False
        clock.advance(2 * MINUTE)
        assert login.reserve(ADDRESS) is True

    def test_a_stale_count_starts_over(self, login, clock):
        """
        GIVEN five confirmed failures followed by a quiet window
        WHEN nine more attempts arrive
        THEN every one is granted and the account is not locked
        """
        for _ in range(5):
            _attempt(login, clock, gap=1)
        clock.advance(16 * MINUTE)

        assert all(_attempt(login, clock, gap=1) for _ in range(9))

        assert login.is_locked(ADDRESS) is False

    def test_a_new_key_gets_the_window_and_reserve_alone_leaves_an_old_one_be(
        self, login, stored, clock
    ):
        """
        GIVEN a reservation on a fresh identifier
        THEN the stored window is the full one
        WHEN ten minutes pass and a second reservation is taken
        THEN the window has run down by ten minutes, and confirming the failure restarts it
        """
        login.reserve(ADDRESS)
        assert stored.seconds_left() == pytest.approx(WINDOW_SECONDS, abs=1)

        clock.advance(10 * MINUTE)
        login.reserve(ADDRESS)
        assert stored.seconds_left() == pytest.approx(WINDOW_SECONDS - 10 * MINUTE, abs=1)

        login.confirm_failure(ADDRESS)
        assert stored.seconds_left() == pytest.approx(WINDOW_SECONDS, abs=1)
        assert stored.count() == 2

    def test_a_count_above_the_limit_is_refused_and_left_alone(self, login, stored, clock):
        """
        GIVEN twelve failures recorded the old way, past the limit
        WHEN a slot is asked for
        THEN it is refused and neither the count nor the window changes
        """
        _fail(login, clock, times=12)
        left = stored.seconds_left()

        assert login.reserve(ADDRESS) is False

        assert stored.count() == 12
        assert stored.seconds_left() == left


class TestLoginRelease:
    """A slot that was neither a failure nor a success is given back, window untouched."""

    def test_release_gives_the_count_back_and_leaves_the_window_where_it_was(
        self, login, stored, clock
    ):
        """
        GIVEN five failures at the start, then a slot taken and released at minute 14
        WHEN a failure arrives at minute 20
        THEN the count is 1, not 6, because the release did not restart the window
        """
        _fail(login, clock, times=5, gap=0)
        clock.advance(14 * MINUTE)
        assert login.reserve(ADDRESS) is True
        assert stored.count() == 6

        login.release(ADDRESS)
        assert stored.count() == 5

        clock.advance(6 * MINUTE)
        login.record_failure(ADDRESS)
        assert stored.count() == 1

    def test_reserve_and_release_on_a_fresh_identifier_leave_nothing(self, login, stored):
        """
        GIVEN an identifier with no history
        WHEN a slot is taken and released
        THEN no key is left behind
        """
        login.reserve(ADDRESS)
        login.release(ADDRESS)

        assert stored.count() is None

    def test_release_on_a_missing_key_leaves_nothing(self, login, stored):
        """
        GIVEN an identifier with no history
        WHEN a slot is released without having been taken
        THEN no key appears and no negative count is stored
        """
        login.release(ADDRESS)

        assert stored.count() is None


class TestLoginConfirmFailure:
    """A confirmed failure restarts the window, and is not lost when the key is gone."""

    def test_confirm_after_a_reset_leaves_a_count_of_one_with_a_window(self, login, stored):
        """
        GIVEN a slot taken, then a reset (a successful login elsewhere) during the password check
        WHEN the check fails and the failure is confirmed
        THEN the count is 1 and a full window runs
        """
        login.reserve(ADDRESS)
        login.reset(ADDRESS)

        login.confirm_failure(ADDRESS)

        assert stored.count() == 1
        assert stored.seconds_left() == pytest.approx(WINDOW_SECONDS, abs=1)

    def test_confirm_after_an_expiry_leaves_a_count_of_one_with_a_window(
        self, login, stored, clock
    ):
        """
        GIVEN a slot taken, and a password check slow enough for the window to pass
        WHEN the failure is confirmed
        THEN the count is 1 and a full window runs
        """
        login.reserve(ADDRESS)
        clock.advance(WINDOW_SECONDS + MINUTE)

        login.confirm_failure(ADDRESS)

        assert stored.count() == 1
        assert stored.seconds_left() == pytest.approx(WINDOW_SECONDS, abs=1)


class TestEmailWindow:
    """The daily total is a fixed window from the first send, with a cooldown inside it."""

    def test_the_window_runs_from_the_first_send_not_the_latest(self, email, clock):
        """
        GIVEN five sends in 23 hours, so a sixth is refused by the daily cap
        WHEN a send is asked for just past 24 hours after the FIRST
        THEN it is allowed, and the new window then holds five sends of its own
        """
        _fill_the_day(email, clock)
        assert _send(email, clock, 2 * MINUTE) is False
        clock.advance(HOUR)

        outcomes = [email.allow(ADDRESS)] + [_send(email, clock, 2 * MINUTE) for _ in range(5)]

        assert outcomes == [True, True, True, True, True, False]

    def test_a_cooldown_refusal_spends_nothing(self, email, clock):
        """
        GIVEN a send followed by three attempts inside the cooldown
        WHEN four more sends are spaced past it
        THEN all of them are allowed and the next is the one the cap refuses
        """
        assert email.allow(ADDRESS) is True
        assert [_send(email, clock, 10) for _ in range(3)] == [False] * 3

        outcomes = [_send(email, clock, 2 * MINUTE) for _ in range(5)]

        assert outcomes == [True, True, True, True, False]

    def test_a_cap_refusal_restarts_the_cooldown(self, email, clock):
        """
        GIVEN a full day and a sixth ask 30 seconds before the window ends
        WHEN a send comes 10 seconds after the window ends
        THEN the cooldown that refusal started still holds, and it clears 40 seconds on
        """
        _fill_the_day(email, clock)
        clock.advance(HOUR - 30)
        assert email.allow(ADDRESS) is False

        assert _send(email, clock, 40) is False
        assert _send(email, clock, 31) is True

    def test_record_counts_toward_the_cap(self, email, clock):
        """
        GIVEN a send that happened anyway and was recorded
        WHEN more sends are asked for, spaced past the cooldown
        THEN four are allowed and the fifth is refused, five slots in all
        """
        email.record(ADDRESS)

        outcomes = [_send(email, clock, 2 * MINUTE) for _ in range(5)]

        assert outcomes == [True, True, True, True, False]

    def test_record_restarts_the_cooldown(self, email, clock):
        """
        GIVEN a send recorded 50 seconds after another
        WHEN an ask comes 30 seconds after the second record
        THEN it is refused, since the record restarted the cooldown
        """
        email.record(ADDRESS)
        clock.advance(50)
        email.record(ADDRESS)

        assert _send(email, clock, 30) is False
        assert _send(email, clock, 31) is True
