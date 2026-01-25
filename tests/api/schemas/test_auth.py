"""Tests for authentication schemas and validators."""

import pytest
from pydantic import ValidationError

from api.schemas.auth import (
    ChangePasswordRequest,
    RegisterRequest,
    UpdateUserRequest,
    validate_name_format,
    validate_password_strength,
)


class TestValidatePasswordStrength:
    """Tests for validate_password_strength function."""

    def test_valid_password_accepted(self):
        """
        GIVEN a password meeting all requirements
        WHEN validate_password_strength is called
        THEN the password is returned unchanged
        """
        # GIVEN
        password = "SecurePass123!"

        # WHEN
        result = validate_password_strength(password)

        # THEN
        assert result == password

    def test_missing_uppercase_rejected(self):
        """
        GIVEN a password without uppercase letters
        WHEN validate_password_strength is called
        THEN ValueError is raised
        """
        # GIVEN
        password = "securepass123!"

        # WHEN/THEN
        with pytest.raises(ValueError, match="uppercase"):
            validate_password_strength(password)

    def test_missing_lowercase_rejected(self):
        """
        GIVEN a password without lowercase letters
        WHEN validate_password_strength is called
        THEN ValueError is raised
        """
        # GIVEN
        password = "SECUREPASS123!"

        # WHEN/THEN
        with pytest.raises(ValueError, match="lowercase"):
            validate_password_strength(password)

    def test_missing_digit_rejected(self):
        """
        GIVEN a password without digits
        WHEN validate_password_strength is called
        THEN ValueError is raised
        """
        # GIVEN
        password = "SecurePassword!"

        # WHEN/THEN
        with pytest.raises(ValueError, match="digit"):
            validate_password_strength(password)

    def test_missing_special_char_rejected(self):
        """
        GIVEN a password without special characters
        WHEN validate_password_strength is called
        THEN ValueError is raised
        """
        # GIVEN
        password = "SecurePass12345"

        # WHEN/THEN
        with pytest.raises(ValueError, match="special"):
            validate_password_strength(password)


class TestValidateNameFormat:
    """Tests for validate_name_format function."""

    def test_valid_name_accepted(self):
        """
        GIVEN a valid name with letters
        WHEN validate_name_format is called
        THEN the name is returned unchanged
        """
        # GIVEN
        name = "John"

        # WHEN
        result = validate_name_format(name)

        # THEN
        assert result == name

    def test_name_with_hyphen_accepted(self):
        """
        GIVEN a name with hyphen
        WHEN validate_name_format is called
        THEN the name is returned unchanged
        """
        # GIVEN
        name = "Mary-Jane"

        # WHEN
        result = validate_name_format(name)

        # THEN
        assert result == name

    def test_name_with_apostrophe_accepted(self):
        """
        GIVEN a name with apostrophe
        WHEN validate_name_format is called
        THEN the name is returned unchanged
        """
        # GIVEN
        name = "O'Connor"

        # WHEN
        result = validate_name_format(name)

        # THEN
        assert result == name

    def test_unicode_letters_accepted(self):
        """
        GIVEN a name with Unicode letters (Cyrillic)
        WHEN validate_name_format is called
        THEN the name is returned unchanged
        """
        # GIVEN
        name = "Иван"

        # WHEN
        result = validate_name_format(name)

        # THEN
        assert result == name

    def test_name_with_digits_rejected(self):
        """
        GIVEN a name containing digits
        WHEN validate_name_format is called
        THEN ValueError is raised
        """
        # GIVEN
        name = "John123"

        # WHEN/THEN
        with pytest.raises(ValueError, match="letters"):
            validate_name_format(name)

    def test_name_with_special_chars_rejected(self):
        """
        GIVEN a name with invalid special characters
        WHEN validate_name_format is called
        THEN ValueError is raised
        """
        # GIVEN
        name = "John@Doe"

        # WHEN/THEN
        with pytest.raises(ValueError, match="letters"):
            validate_name_format(name)


class TestRegisterRequest:
    """Tests for RegisterRequest schema."""

    def test_valid_registration_accepted(self):
        """
        GIVEN valid registration data
        WHEN RegisterRequest is created
        THEN no error is raised
        """
        # WHEN
        request = RegisterRequest(
            email="test@example.com",
            password="SecurePass123!",
            first_name="John",
            last_name="Doe",
        )

        # THEN
        assert request.email == "test@example.com"
        assert request.first_name == "John"

    def test_non_ascii_email_rejected(self):
        """
        GIVEN email with non-ASCII characters
        WHEN RegisterRequest is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="ASCII"):
            RegisterRequest(
                email="тест@example.com",
                password="SecurePass123!",
                first_name="John",
                last_name="Doe",
            )

    def test_weak_password_rejected(self):
        """
        GIVEN a weak password
        WHEN RegisterRequest is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="uppercase"):
            RegisterRequest(
                email="test@example.com",
                password="weakpassword1!",
                first_name="John",
                last_name="Doe",
            )

    def test_invalid_first_name_rejected(self):
        """
        GIVEN invalid first name with digits
        WHEN RegisterRequest is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="letters"):
            RegisterRequest(
                email="test@example.com",
                password="SecurePass123!",
                first_name="John123",
                last_name="Doe",
            )

    def test_invalid_last_name_rejected(self):
        """
        GIVEN invalid last name with special characters
        WHEN RegisterRequest is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="letters"):
            RegisterRequest(
                email="test@example.com",
                password="SecurePass123!",
                first_name="John",
                last_name="Doe@123",
            )


class TestUpdateUserRequest:
    """Tests for UpdateUserRequest schema."""

    def test_valid_update_accepted(self):
        """
        GIVEN valid update data
        WHEN UpdateUserRequest is created
        THEN no error is raised
        """
        # WHEN
        request = UpdateUserRequest(first_name="Jane", last_name="Smith")

        # THEN
        assert request.first_name == "Jane"
        assert request.last_name == "Smith"

    def test_empty_string_converted_to_none(self):
        """
        GIVEN empty string for first_name
        WHEN UpdateUserRequest is created
        THEN empty string is converted to None
        """
        # WHEN
        request = UpdateUserRequest(first_name="", last_name="Smith")

        # THEN
        assert request.first_name is None
        assert request.last_name == "Smith"

    def test_none_values_preserved(self):
        """
        GIVEN None for both fields
        WHEN UpdateUserRequest is created
        THEN None values are preserved
        """
        # WHEN
        request = UpdateUserRequest(first_name=None, last_name=None)

        # THEN
        assert request.first_name is None
        assert request.last_name is None

    def test_invalid_name_rejected(self):
        """
        GIVEN invalid name with digits
        WHEN UpdateUserRequest is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="letters"):
            UpdateUserRequest(first_name="John123")


class TestChangePasswordRequest:
    """Tests for ChangePasswordRequest schema."""

    def test_valid_password_change_accepted(self):
        """
        GIVEN valid current and new passwords
        WHEN ChangePasswordRequest is created
        THEN no error is raised
        """
        # WHEN
        request = ChangePasswordRequest(
            current_password="old_password",
            new_password="NewSecure123!",
        )

        # THEN
        assert request.current_password == "old_password"
        assert request.new_password == "NewSecure123!"

    def test_weak_new_password_rejected(self):
        """
        GIVEN weak new password
        WHEN ChangePasswordRequest is created
        THEN ValidationError is raised
        """
        # WHEN/THEN
        with pytest.raises(ValidationError, match="uppercase"):
            ChangePasswordRequest(
                current_password="old_password",
                new_password="weakpassword1!",
            )
