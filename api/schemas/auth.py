"""Authentication schemas."""

import re

import regex
from pydantic import BaseModel, EmailStr, Field, field_validator

NAME_PATTERN = regex.compile(r"^[\p{L}\s'-]+$")


def validate_password_strength(password: str) -> str:
    """Validate password meets strength requirements.

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
    return password


def validate_name_format(name: str) -> str:
    """Validate name contains only letters, spaces, hyphens, and apostrophes.

    :param name: Name to validate
    :return: Name if valid
    :raises ValueError: If name contains invalid characters
    """
    if not NAME_PATTERN.match(name):
        raise ValueError(
            "Name can only contain letters, spaces, hyphens, and apostrophes"
        )
    return name


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(..., max_length=255, description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str | None = Field(None, max_length=100, description="Last name")

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
    def last_name_format(cls, v: str | None) -> str | None:
        """Validate last name format."""
        if v is None:
            return v
        return validate_name_format(v)


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    first_name: str
    last_name: str | None
    photo_url: str | None


class UpdateUserRequest(BaseModel):
    """User profile update request."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    photo_url: str | None = Field(None, max_length=500)

    @field_validator("first_name")
    @classmethod
    def first_name_format(cls, v: str | None) -> str | None:
        """Validate first name format."""
        if v is None:
            return v
        return validate_name_format(v)

    @field_validator("last_name")
    @classmethod
    def last_name_format(cls, v: str | None) -> str | None:
        """Validate last name format."""
        if v is None:
            return v
        return validate_name_format(v)


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        return validate_password_strength(v)
