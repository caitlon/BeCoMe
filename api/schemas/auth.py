"""Authentication schemas."""

import re
from typing import TYPE_CHECKING

import regex
from pydantic import BaseModel, EmailStr, Field, field_validator

from api.utils.photo_links import build_photo_url

if TYPE_CHECKING:
    from api.db.models import User

NAME_PATTERN = regex.compile(r"^[\p{L}\s'-]+$")


def validate_password_strength(password: str) -> str:
    """Validate password meets strength requirements.

    Requirements: 12+ chars, uppercase, lowercase, digit, special character.

    :param password: Password to validate
    :return: Password if valid
    :raises ValueError: If password doesn't meet requirements
    """
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_=+\[\]\\;'/`~]", password):
        raise ValueError("Password must contain at least one special character")
    return password


def validate_name_format(name: str) -> str:
    """Validate name contains only letters, spaces, hyphens, and apostrophes.

    :param name: Name to validate
    :return: Name if valid
    :raises ValueError: If name contains invalid characters
    """
    if not NAME_PATTERN.match(name):
        raise ValueError("Name can only contain letters, spaces, hyphens, and apostrophes")
    return name


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(..., max_length=255, description="Email address")
    password: str = Field(..., min_length=12, max_length=128, description="Password")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")

    @field_validator("email")
    @classmethod
    def email_ascii_only(cls, v: str) -> str:
        """Validate email contains only ASCII characters."""
        if not v.isascii():
            raise ValueError("Email must contain only ASCII characters")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        return validate_password_strength(v)

    @field_validator("first_name")
    @classmethod
    def first_name_format(cls, v: str) -> str:
        """Validate first name format."""
        return validate_name_format(v)

    @field_validator("last_name")
    @classmethod
    def last_name_format(cls, v: str) -> str:
        """Validate last name format."""
        return validate_name_format(v)


class TokenResponse(BaseModel):
    """JWT token response with optional refresh token."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = 0  # Access token lifetime in seconds


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    first_name: str
    last_name: str
    photo_url: str | None = None

    @classmethod
    def from_user(cls, user: "User") -> "UserResponse":
        """Build the response from a user model, resolving the photo proxy URL.

        :param user: User database model.
        :return: UserResponse with a public photo URL, or None when unset.
        """
        return cls(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            photo_url=build_photo_url(user.id, user.photo_url),
        )


class UpdateUserRequest(BaseModel):
    """User profile update request."""

    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)

    @field_validator("first_name")
    @classmethod
    def first_name_format(cls, v: str | None) -> str | None:
        """Validate first name format. Convert empty string to None."""
        if v is None or v == "":
            return None
        return validate_name_format(v)

    @field_validator("last_name")
    @classmethod
    def last_name_format(cls, v: str | None) -> str | None:
        """Validate last name format. Convert empty string to None."""
        if v is None or v == "":
            return None
        return validate_name_format(v)


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=12, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        return validate_password_strength(v)


class ForgotPasswordRequest(BaseModel):
    """Password reset request by email."""

    email: EmailStr = Field(..., max_length=255, description="Email address")

    @field_validator("email")
    @classmethod
    def email_ascii_only(cls, v: str) -> str:
        """Validate email contains only ASCII characters."""
        if not v.isascii():
            raise ValueError("Email must contain only ASCII characters")
        return v


class ResetPasswordRequest(BaseModel):
    """Password reset confirmation with a token and the new password."""

    token: str = Field(..., min_length=1, max_length=512, description="Reset token")
    new_password: str = Field(..., min_length=12, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        return validate_password_strength(v)
