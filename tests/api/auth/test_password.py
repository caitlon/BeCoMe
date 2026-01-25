"""Unit tests for password hashing and verification."""

import pytest

from api.auth.password import hash_password, verify_password


class TestHashPassword:
    """Tests for hash_password function."""

    def test_returns_string(self):
        """Hash is returned as a string."""
        # GIVEN
        password = "secretpassword123"

        # WHEN
        hashed = hash_password(password)

        # THEN
        assert isinstance(hashed, str)

    def test_returns_bcrypt_format(self):
        """Hash follows bcrypt format ($2b$...)."""
        # GIVEN
        password = "mypassword"

        # WHEN
        hashed = hash_password(password)

        # THEN
        assert hashed.startswith("$2b$")

    def test_different_passwords_produce_different_hashes(self):
        """Different passwords result in different hashes."""
        # GIVEN
        password1 = "password_one"
        password2 = "password_two"

        # WHEN
        hash1 = hash_password(password1)
        hash2 = hash_password(password2)

        # THEN
        assert hash1 != hash2

    def test_same_password_produces_different_hashes(self):
        """Same password hashed twice produces different hashes (due to salt)."""
        # GIVEN
        password = "samepassword"

        # WHEN
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # THEN
        assert hash1 != hash2

    def test_handles_long_password(self):
        """Passwords longer than 72 bytes work correctly."""
        # GIVEN - password longer than bcrypt's native 72-byte limit
        long_password = "a" * 200

        # WHEN
        hashed = hash_password(long_password)

        # THEN
        assert verify_password(long_password, hashed)

    def test_handles_unicode_password(self):
        """Unicode characters in password work correctly."""
        # GIVEN
        unicode_password = "\u043f\u0430\u0440\u043e\u043b\u044c123!@#"  # Cyrillic characters

        # WHEN
        hashed = hash_password(unicode_password)

        # THEN
        assert verify_password(unicode_password, hashed)

    def test_handles_empty_string(self):
        """Empty string can be hashed (though not recommended)."""
        # GIVEN
        empty_password = ""

        # WHEN
        hashed = hash_password(empty_password)

        # THEN
        assert isinstance(hashed, str)
        assert verify_password(empty_password, hashed)


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_correct_password_returns_true(self):
        """Correct password verification returns True."""
        # GIVEN
        password = "correctpassword"
        hashed = hash_password(password)

        # WHEN
        result = verify_password(password, hashed)

        # THEN
        assert result is True

    def test_wrong_password_returns_false(self):
        """Wrong password verification returns False."""
        # GIVEN
        password = "correctpassword"
        hashed = hash_password(password)

        # WHEN
        result = verify_password("wrongpassword", hashed)

        # THEN
        assert result is False

    def test_similar_password_returns_false(self):
        """Similar but not identical password returns False."""
        # GIVEN
        password = "MyPassword123"
        hashed = hash_password(password)

        # WHEN
        result = verify_password("mypassword123", hashed)  # lowercase

        # THEN
        assert result is False

    def test_invalid_hash_raises_error(self):
        """Invalid hash format raises ValueError."""
        # GIVEN
        password = "anypassword"
        invalid_hash = "not-a-valid-bcrypt-hash"

        # WHEN / THEN
        with pytest.raises(ValueError):
            verify_password(password, invalid_hash)

    def test_multiple_verifications_work(self):
        """Same hash can be verified multiple times."""
        # GIVEN
        password = "reusablepassword"
        hashed = hash_password(password)

        # WHEN / THEN
        assert verify_password(password, hashed)
        assert verify_password(password, hashed)
        assert verify_password(password, hashed)

    def test_long_password_distinction(self):
        """Long passwords differing after 72 bytes are still distinguished."""
        # GIVEN - SHA256 pre-hashing ensures full password is used
        password1 = "a" * 100 + "X"
        password2 = "a" * 100 + "Y"

        hashed1 = hash_password(password1)

        # WHEN / THEN
        assert verify_password(password1, hashed1)
        assert not verify_password(password2, hashed1)
