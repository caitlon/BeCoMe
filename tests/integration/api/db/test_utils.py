"""Tests for database utility functions."""

from datetime import UTC, datetime, timedelta

from api.db.utils import ensure_utc, utc_now


class TestUtcNow:
    """Tests for utc_now utility function."""

    def test_returns_timezone_aware_datetime(self):
        """
        GIVEN utc_now function
        WHEN called
        THEN returns datetime with UTC timezone
        """
        # WHEN
        result = utc_now()

        # THEN
        assert result.tzinfo is not None
        assert result.tzinfo == UTC

    def test_returns_current_time_approximately(self):
        """
        GIVEN utc_now function
        WHEN called
        THEN returns time within reasonable range of actual current time
        """
        # GIVEN
        before = datetime.now(UTC)

        # WHEN
        result = utc_now()

        # THEN
        after = datetime.now(UTC)
        assert before <= result <= after


class TestEnsureUtc:
    """Tests for ensure_utc utility function."""

    def test_naive_datetime_gets_utc_timezone(self):
        """
        GIVEN a naive datetime (no timezone)
        WHEN passed to ensure_utc
        THEN returns datetime with UTC timezone
        """
        # GIVEN
        naive = datetime(2024, 1, 15, 12, 0, 0)
        assert naive.tzinfo is None

        # WHEN
        result = ensure_utc(naive)

        # THEN
        assert result.tzinfo == UTC
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_aware_datetime_unchanged(self):
        """
        GIVEN a timezone-aware datetime with UTC
        WHEN passed to ensure_utc
        THEN returns same datetime unchanged
        """
        # GIVEN
        aware = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        # WHEN
        result = ensure_utc(aware)

        # THEN
        assert result == aware
        assert result.tzinfo == UTC

    def test_non_utc_aware_datetime_unchanged(self):
        """
        GIVEN a timezone-aware datetime with non-UTC timezone
        WHEN passed to ensure_utc
        THEN returns same datetime unchanged (does not convert to UTC)

        Note: ensure_utc only adds UTC to naive datetimes,
        it does not convert between timezones.
        """
        from datetime import timezone

        # GIVEN: create datetime with +05:00 offset
        offset = timezone(timedelta(hours=5))
        aware_non_utc = datetime(2024, 1, 15, 12, 0, 0, tzinfo=offset)

        # WHEN
        result = ensure_utc(aware_non_utc)

        # THEN: should be unchanged
        assert result == aware_non_utc
        assert result.tzinfo == offset
