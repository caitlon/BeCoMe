"""Pydantic schemas for API request/response validation."""

import math
from datetime import datetime
from typing import Self

from pydantic import BaseModel, EmailStr, Field, model_validator

from src.models.fuzzy_number import FuzzyTriangleNumber


class ExpertInput(BaseModel):
    """Single expert opinion input."""

    name: str = Field(..., min_length=1, description="Expert name or identifier")
    lower: float = Field(..., description="Lower bound (pessimistic estimate)")
    peak: float = Field(..., description="Peak value (most likely)")
    upper: float = Field(..., description="Upper bound (optimistic estimate)")

    @model_validator(mode="after")
    def validate_fuzzy_constraints(self) -> Self:
        """Validate: finite values and lower <= peak <= upper."""
        values = [self.lower, self.peak, self.upper]
        if not all(math.isfinite(v) for v in values):
            msg = "Values must be finite (no NaN or infinity)"
            raise ValueError(msg)
        if not (self.lower <= self.peak <= self.upper):
            msg = f"Must satisfy: lower <= peak <= upper. Got: {self.lower}, {self.peak}, {self.upper}"
            raise ValueError(msg)
        return self


class CalculateRequest(BaseModel):
    """Request body for calculation endpoint."""

    experts: list[ExpertInput] = Field(..., min_length=1, description="List of expert opinions")


class FuzzyNumberOutput(BaseModel):
    """Fuzzy triangular number in response."""

    lower: float
    peak: float
    upper: float
    centroid: float

    @classmethod
    def from_domain(cls, fuzzy: FuzzyTriangleNumber) -> "FuzzyNumberOutput":
        """Create from domain FuzzyTriangleNumber."""
        return cls(
            lower=fuzzy.lower_bound,
            peak=fuzzy.peak,
            upper=fuzzy.upper_bound,
            centroid=fuzzy.centroid,
        )


class CalculateResponse(BaseModel):
    """Response from calculation endpoint."""

    best_compromise: FuzzyNumberOutput
    arithmetic_mean: FuzzyNumberOutput
    median: FuzzyNumberOutput
    max_error: float
    num_experts: int


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str


# --- Auth Schemas ---


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(..., max_length=255, description="Email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str | None = Field(None, max_length=100, description="Last name")


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


# --- Project Schemas ---


class ProjectCreate(BaseModel):
    """Request to create a new project."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: str | None = Field(None, max_length=2000, description="Project description")
    scale_min: float = Field(default=0.0, description="Minimum scale value")
    scale_max: float = Field(default=100.0, description="Maximum scale value")
    scale_unit: str = Field(
        default="", max_length=50, description="Scale unit (e.g., '%', 'points')"
    )

    @model_validator(mode="after")
    def validate_scale(self) -> Self:
        """Validate scale_min < scale_max."""
        if self.scale_min >= self.scale_max:
            msg = f"scale_min ({self.scale_min}) must be less than scale_max ({self.scale_max})"
            raise ValueError(msg)
        return self


class ProjectUpdate(BaseModel):
    """Request to update a project (partial update)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    scale_min: float | None = None
    scale_max: float | None = None
    scale_unit: str | None = Field(None, max_length=50)


class ProjectResponse(BaseModel):
    """Project details response."""

    id: str
    name: str
    description: str | None
    scale_min: float
    scale_max: float
    scale_unit: str
    admin_id: str
    created_at: datetime
    member_count: int


class MemberResponse(BaseModel):
    """Project member details."""

    user_id: str
    email: str
    first_name: str
    last_name: str | None
    role: str
    joined_at: datetime
