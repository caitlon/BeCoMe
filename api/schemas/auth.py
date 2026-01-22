"""Authentication schemas."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator


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


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        return validate_password_strength(v)
