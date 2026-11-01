"""The in-memory throttles keep the same windows as their Redis twins.

Each scenario runs against both backends of a throttle with one controlled clock, so a
drift in either fails here. The Redis side takes its time from fakeredis' socket module, the
in-memory side from the throttle module's ``datetime``; the fixture points both at one clock.
Scenarios stay clear of the exact instant a window ends, where Redis (key kept until the
clock passes expiry) and the in-memory backends (state dropped at it) differ by one instant.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import fakeredis
import pytest

from api.auth import email_throttle, login_throttle
from api.auth.email_throttle import InMemoryEmailSendThrottle, RedisEmailSendThrottle
from api.auth.login_throttle import InMemoryLoginThrottle, RedisLoginThrottle

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
