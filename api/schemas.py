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


# --- Invitation Schemas ---


class InvitationCreate(BaseModel):
    """Request to create a project invitation."""

    expires_in_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Days until invitation expires (1-90)",
    )


class InvitationResponse(BaseModel):
    """Response after creating an invitation."""

    token: str
    expires_at: datetime
    project_id: str
    project_name: str


class InvitationInfoResponse(BaseModel):
    """Public information about an invitation."""

    project_name: str
    project_description: str | None
    admin_name: str
    expires_at: datetime
    is_valid: bool


# --- Opinion Schemas ---


class OpinionCreate(BaseModel):
    """Request to create or update an expert opinion."""

    position: str = Field(default="", max_length=255, description="Expert's position/role")
    lower_bound: float = Field(..., description="Lower bound (pessimistic estimate)")
    peak: float = Field(..., description="Peak value (most likely)")
    upper_bound: float = Field(..., description="Upper bound (optimistic estimate)")

    @model_validator(mode="after")
    def validate_fuzzy_constraints(self) -> Self:
        """Validate: finite values and lower <= peak <= upper."""
        values = [self.lower_bound, self.peak, self.upper_bound]
        if not all(math.isfinite(v) for v in values):
            msg = "Values must be finite (no NaN or infinity)"
            raise ValueError(msg)
        if not (self.lower_bound <= self.peak <= self.upper_bound):
            msg = (
                f"Must satisfy: lower_bound <= peak <= upper_bound. "
                f"Got: {self.lower_bound}, {self.peak}, {self.upper_bound}"
            )
            raise ValueError(msg)
        return self


class OpinionResponse(BaseModel):
    """Expert opinion response with user details."""

    id: str
    user_id: str
    user_email: str
    user_first_name: str
    user_last_name: str | None
    position: str
    lower_bound: float
    peak: float
    upper_bound: float
    centroid: float
    created_at: datetime
    updated_at: datetime


# --- Calculation Result Schemas ---


class FuzzyNumberResult(BaseModel):
    """Fuzzy triangular number in calculation result."""

    lower: float
    peak: float
    upper: float
    centroid: float


class CalculationResultResponse(BaseModel):
    """BeCoMe calculation result for a project."""

    best_compromise: FuzzyNumberResult
    arithmetic_mean: FuzzyNumberResult
    median: FuzzyNumberResult
    max_error: float
    num_experts: int
    likert_value: int | None
    likert_decision: str | None
    calculated_at: datetime
