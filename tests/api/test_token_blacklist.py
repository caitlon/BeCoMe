"""Unit tests for token blacklist service."""

from datetime import UTC, datetime, timedelta

from api.auth.token_blacklist import TokenBlacklist


class TestTokenBlacklistAdd:
    """Tests for TokenBlacklist.add method."""

    def setup_method(self):
        """Reset blacklist before each test."""
        TokenBlacklist.reset()

    def test_adds_jti_to_store(self):
        """JTI is added to blacklist store."""
        # GIVEN
        jti = "test-jti-001"
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        # WHEN
        TokenBlacklist.add(jti, expires_at)

        # THEN
        assert TokenBlacklist.is_blacklisted(jti) is True

    def test_ignores_already_expired_token(self):
        """Token that is already expired is not added to blacklist."""
        # GIVEN
        jti = "expired-jti-001"
        expires_at = datetime.now(UTC) - timedelta(hours=1)

        # WHEN
        TokenBlacklist.add(jti, expires_at)

        # THEN
        assert TokenBlacklist.is_blacklisted(jti) is False

    def test_handles_naive_datetime(self):
        """Naive datetime is converted to UTC."""
        # GIVEN
        jti = "naive-jti-001"
        expires_at = datetime.now() + timedelta(hours=1)  # Naive datetime

        # WHEN
        TokenBlacklist.add(jti, expires_at)

        # THEN
        assert TokenBlacklist.is_blacklisted(jti) is True

    def test_multiple_tokens_can_be_added(self):
        """Multiple tokens can be added to blacklist."""
        # GIVEN
        jti1 = "multi-jti-001"
        jti2 = "multi-jti-002"
        jti3 = "multi-jti-003"
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        # WHEN
        TokenBlacklist.add(jti1, expires_at)
        TokenBlacklist.add(jti2, expires_at)
        TokenBlacklist.add(jti3, expires_at)

        # THEN
        assert TokenBlacklist.is_blacklisted(jti1) is True
        assert TokenBlacklist.is_blacklisted(jti2) is True
        assert TokenBlacklist.is_blacklisted(jti3) is True


class TestTokenBlacklistIsBlacklisted:
    """Tests for TokenBlacklist.is_blacklisted method."""

    def setup_method(self):
        """Reset blacklist before each test."""
        TokenBlacklist.reset()

    def test_returns_true_for_blacklisted(self):
        """Returns True for blacklisted JTI."""
        # GIVEN
        jti = "blacklisted-jti"
        TokenBlacklist.add(jti, datetime.now(UTC) + timedelta(hours=1))

        # WHEN
        result = TokenBlacklist.is_blacklisted(jti)

        # THEN
        assert result is True

    def test_returns_false_for_unknown(self):
        """Returns False for unknown JTI."""
        # GIVEN
        unknown_jti = "unknown-jti-12345"

        # WHEN
        result = TokenBlacklist.is_blacklisted(unknown_jti)

        # THEN
        assert result is False

    def test_auto_removes_expired_on_check(self):
        """Expired entry is automatically removed on is_blacklisted check."""
        # GIVEN
        jti = "auto-remove-jti"
        # Add with very short expiration
        TokenBlacklist._memory_store[jti] = datetime.now(UTC) - timedelta(seconds=1)

        # WHEN
        result = TokenBlacklist.is_blacklisted(jti)

        # THEN
        assert result is False
        assert jti not in TokenBlacklist._memory_store

    def test_handles_naive_datetime_in_store(self):
        """Handles naive datetime in store when checking."""
        # GIVEN
        jti = "naive-store-jti"
        # Directly add naive datetime to store
        TokenBlacklist._memory_store[jti] = datetime.now() + timedelta(hours=1)

        # WHEN
        result = TokenBlacklist.is_blacklisted(jti)

        # THEN
        assert result is True


class TestTokenBlacklistCleanupExpired:
    """Tests for TokenBlacklist.cleanup_expired method."""

    def setup_method(self):
        """Reset blacklist before each test."""
        TokenBlacklist.reset()

    def test_removes_expired_entries(self):
        """Cleanup removes all expired entries."""
        # GIVEN
        expired_jti1 = "expired-cleanup-001"
        expired_jti2 = "expired-cleanup-002"
        TokenBlacklist._memory_store[expired_jti1] = datetime.now(UTC) - timedelta(hours=1)
        TokenBlacklist._memory_store[expired_jti2] = datetime.now(UTC) - timedelta(minutes=30)

        # WHEN
        removed = TokenBlacklist.cleanup_expired()

        # THEN
        assert removed == 2
        assert expired_jti1 not in TokenBlacklist._memory_store
        assert expired_jti2 not in TokenBlacklist._memory_store

    def test_returns_count_of_removed(self):
        """Cleanup returns correct count of removed entries."""
        # GIVEN
        for i in range(5):
            TokenBlacklist._memory_store[f"expired-{i}"] = datetime.now(UTC) - timedelta(hours=1)

        # WHEN
        removed = TokenBlacklist.cleanup_expired()

        # THEN
        assert removed == 5

    def test_keeps_valid_entries(self):
        """Cleanup keeps entries that are still valid."""
        # GIVEN
        valid_jti = "valid-jti-cleanup"
        expired_jti = "expired-jti-cleanup"
        TokenBlacklist._memory_store[valid_jti] = datetime.now(UTC) + timedelta(hours=1)
        TokenBlacklist._memory_store[expired_jti] = datetime.now(UTC) - timedelta(hours=1)

        # WHEN
        removed = TokenBlacklist.cleanup_expired()

        # THEN
        assert removed == 1
        assert valid_jti in TokenBlacklist._memory_store
        assert expired_jti not in TokenBlacklist._memory_store

    def test_handles_empty_store(self):
        """Cleanup handles empty store gracefully."""
        # GIVEN - empty store

        # WHEN
        removed = TokenBlacklist.cleanup_expired()

        # THEN
        assert removed == 0

    def test_handles_naive_datetime(self):
        """Cleanup handles naive datetime in store."""
        # GIVEN
        jti = "naive-cleanup-jti"
        TokenBlacklist._memory_store[jti] = datetime.now() - timedelta(hours=1)  # Naive

        # WHEN
        removed = TokenBlacklist.cleanup_expired()

        # THEN
        assert removed == 1
        assert jti not in TokenBlacklist._memory_store


class TestTokenBlacklistReset:
    """Tests for TokenBlacklist.reset method."""

    def test_clears_all_entries(self):
        """Reset clears all entries from store."""
        # GIVEN
        TokenBlacklist.add("reset-jti-1", datetime.now(UTC) + timedelta(hours=1))
        TokenBlacklist.add("reset-jti-2", datetime.now(UTC) + timedelta(hours=1))
        TokenBlacklist.add("reset-jti-3", datetime.now(UTC) + timedelta(hours=1))

        # WHEN
        TokenBlacklist.reset()

        # THEN
        assert TokenBlacklist.is_blacklisted("reset-jti-1") is False
        assert TokenBlacklist.is_blacklisted("reset-jti-2") is False
        assert TokenBlacklist.is_blacklisted("reset-jti-3") is False
