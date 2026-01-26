"""Tests for application configuration."""

from api.config import Settings


class TestSupabaseStorageEnabled:
    """Tests for supabase_storage_enabled property."""

    def test_returns_true_when_both_url_and_key_set(self):
        """
        GIVEN Settings with both supabase_url and supabase_key configured
        WHEN supabase_storage_enabled is accessed
        THEN it returns True
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            supabase_url="https://example.supabase.co",
            supabase_key="test-key-123",
        )

        # WHEN
        result = settings.supabase_storage_enabled

        # THEN
        assert result is True

    def test_returns_false_when_url_missing(self):
        """
        GIVEN Settings with supabase_url missing
        WHEN supabase_storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            supabase_url=None,
            supabase_key="test-key-123",
        )

        # WHEN
        result = settings.supabase_storage_enabled

        # THEN
        assert result is False

    def test_returns_false_when_key_missing(self):
        """
        GIVEN Settings with supabase_key missing
        WHEN supabase_storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            supabase_url="https://example.supabase.co",
            supabase_key=None,
        )

        # WHEN
        result = settings.supabase_storage_enabled

        # THEN
        assert result is False

    def test_returns_false_when_both_missing(self):
        """
        GIVEN Settings with neither supabase_url nor supabase_key configured
        WHEN supabase_storage_enabled is accessed
        THEN it returns False
        """
        # GIVEN
        settings = Settings(
            secret_key="test-secret-key",
            supabase_url=None,
            supabase_key=None,
        )

        # WHEN
        result = settings.supabase_storage_enabled

        # THEN
        assert result is False
