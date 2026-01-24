"""Tests for database utility functions."""

from datetime import UTC, datetime

import pytest

from api.db.utils import EMAIL_REGEX, ensure_utc, utc_now


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


class TestEmailRegex:
    """Tests for EMAIL_REGEX pattern."""

    @pytest.mark.parametrize(
        "email",
        [
            "simple@example.com",
            "very.common@example.com",
            "disposable.style.email.with+symbol@example.com",
            "other.email-with-hyphen@example.com",
            "fully-qualified-domain@example.com",
            "user.name+tag+sorting@example.com",
            "x@example.com",
            "example-indeed@strange-example.com",
            "test@subdomain.example.com",
            "user123@example.co.uk",
            "firstname.lastname@example.org",
            "email@example-one.com",
            "_______@example.com",
            "email@example.name",
        ],
    )
    def test_valid_email_formats_match(self, email: str):
        """
        GIVEN various valid email formats
        WHEN matched against EMAIL_REGEX
        THEN all match successfully
        """
        # WHEN/THEN
        assert EMAIL_REGEX.match(email) is not None

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "plainaddress",
            "@example.com",
            "email@",
            "email@.com",
            "email@example",
            "email@@example.com",
            "email @example.com",
            "email@ example.com",
        ],
    )
    def test_invalid_email_formats_do_not_match(self, invalid_email: str):
        """
        GIVEN various clearly invalid email formats
        WHEN matched against EMAIL_REGEX
        THEN none match
        """
        # WHEN/THEN
        assert EMAIL_REGEX.match(invalid_email) is None

    @pytest.mark.parametrize(
        "permissive_email",
        [
            ".email@example.com",
            "email.@example.com",
            "email@-example.com",
        ],
    )
    def test_permissive_email_formats_accepted(self, permissive_email: str):
        """
        GIVEN edge case emails that EMAIL_REGEX accepts
        WHEN matched against EMAIL_REGEX
        THEN they match (documenting permissive behavior)

        Note: These are technically invalid per RFC but accepted by our regex.
        """
        # WHEN/THEN - documenting current behavior
        assert EMAIL_REGEX.match(permissive_email) is not None
