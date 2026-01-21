"""Expert opinion schemas."""

import math
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


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
