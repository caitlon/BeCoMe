"""Expert opinion schemas."""

from datetime import datetime
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from api.schemas.validators import validate_fuzzy_constraints
from api.utils.sanitization import sanitize_text

if TYPE_CHECKING:
    from api.db.models import ExpertOpinion, User


class OpinionCreate(BaseModel):
    """Request to create or update an expert opinion."""

    position: str = Field(..., min_length=1, max_length=255, description="Expert's position/role")
    lower_bound: float = Field(..., description="Lower bound (pessimistic estimate)")
    peak: float = Field(..., description="Peak value (most likely)")
    upper_bound: float = Field(..., description="Upper bound (optimistic estimate)")

    @field_validator("position", mode="after")
    @classmethod
    def sanitize_position(cls, v: str) -> str:
        """Remove HTML from position field."""
        sanitized = sanitize_text(v).strip()
        if not sanitized:
            msg = "Position must not be empty after sanitization"
            raise ValueError(msg)
        return sanitized

    @model_validator(mode="after")
    def validate_fuzzy(self) -> Self:
        """Validate fuzzy number constraints."""
        validate_fuzzy_constraints(self.lower_bound, self.peak, self.upper_bound)
        return self


class OpinionResponse(BaseModel):
    """Expert opinion response with user details."""

    id: str
    user_id: str
    user_email: str
    user_first_name: str
    user_last_name: str | None = None
    position: str
    lower_bound: float
    peak: float
    upper_bound: float
    centroid: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, opinion: "ExpertOpinion", user: "User") -> "OpinionResponse":
        """Create response from database models.

        :param opinion: ExpertOpinion database model
        :param user: User database model
        :return: OpinionResponse instance
        """
        return cls(
            id=str(opinion.id),
            user_id=str(opinion.user_id),
            user_email=user.email,
            user_first_name=user.first_name,
            user_last_name=user.last_name,
            position=opinion.position,
            lower_bound=opinion.lower_bound,
            peak=opinion.peak,
            upper_bound=opinion.upper_bound,
            centroid=(opinion.lower_bound + opinion.peak + opinion.upper_bound) / 3,
            created_at=opinion.created_at,
            updated_at=opinion.updated_at,
        )
