"""
BeCoMe calculation result representation.

This module provides the BeCoMeResult class for storing the complete
results of a BeCoMe (Best Compromise Mean) calculation.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001

from pydantic import BaseModel, ConfigDict, Field

from .fuzzy_number import FuzzyTriangleNumber


class BeCoMeResult(BaseModel):
    """
    Complete result of a BeCoMe calculation.

    The BeCoMe method calculates a best compromise between the arithmetic mean
    and statistical median of expert opinions. This class stores all intermediate
    and final results.

    Attributes:
        best_compromise: Final result (ΓΩMean) - average of arithmetic mean and median
        arithmetic_mean: Arithmetic mean (Γ) of all expert opinions
        median: Statistical median (Ω) of all expert opinions
        max_error: Maximum error (Δmax) - half the distance between centroids of mean and median
        num_experts: Number of expert opinions used in calculation
        is_even: Whether the number of experts was even (affects median calculation)
    """

    best_compromise: FuzzyTriangleNumber = Field(
        ...,
        description="Best compromise (ΓΩMean): π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2",
    )
    arithmetic_mean: FuzzyTriangleNumber = Field(
        ...,
        description="Arithmetic mean (Γ): α, γ, β",
    )
    median: FuzzyTriangleNumber = Field(
        ...,
        description="Statistical median (Ω): ρ, ω, σ",
    )
    max_error: float = Field(
        ...,
        ge=0.0,
        description="Maximum error (Δmax): |centroid(Γ) - centroid(Ω)| / 2",
    )
    num_experts: int = Field(
        ...,
        ge=1,
        description="Number of expert opinions",
    )
    is_even: bool = Field(
        ...,
        description="True if number of experts is even, False if odd",
    )

    # Pydantic configuration
    model_config = ConfigDict(
        # Allow arbitrary types (for FuzzyTriangleNumber)
        arbitrary_types_allowed=True,
    )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"BeCoMe Result ({self.num_experts} experts, "
            f"{'even' if self.is_even else 'odd'}):\n"
            f"  Best Compromise: {self.best_compromise}\n"
            f"  Arithmetic Mean: {self.arithmetic_mean}\n"
            f"  Median: {self.median}\n"
            f"  Max Error: {self.max_error:.2f}"
        )
