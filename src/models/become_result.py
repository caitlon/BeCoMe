"""
BeCoMe calculation result representation.

This module provides the BeCoMeResult class for storing the complete
results of a BeCoMe (Best Compromise Mean) calculation.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001, RUF003

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .fuzzy_number import FuzzyTriangleNumber


class BeCoMeResult(BaseModel):
    """
    Immutable result of a BeCoMe calculation.

    The BeCoMe method calculates a best compromise between the arithmetic mean
    and statistical median of expert opinions. This class stores all intermediate
    and final results.

    This class is immutable (frozen) to ensure that calculation results
    cannot be accidentally modified after creation, maintaining data integrity.

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

    # Pydantic configuration
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_even(self) -> bool:
        """
        Computed property indicating if the number of experts is even.

        This is a derived property based on num_experts, demonstrating
        the DRY (Don't Repeat Yourself) principle by avoiding storage
        of redundant data.

        Returns:
            True if number of experts is even, False if odd

        Example:
            >>> result = BeCoMeResult(...)
            >>> result.num_experts
            5
            >>> result.is_even
            False
        """
        return self.num_experts % 2 == 0

    @classmethod
    def from_calculations(
        cls,
        arithmetic_mean: FuzzyTriangleNumber,
        median: FuzzyTriangleNumber,
        num_experts: int,
    ) -> "BeCoMeResult":
        """
        Factory method to create BeCoMeResult from mean and median calculations.

        This factory method encapsulates the logic for calculating the best compromise
        and maximum error from the arithmetic mean and median. It demonstrates the
        Factory Method pattern and provides a clean interface for creating results.

        The method automatically calculates:
        - Best compromise: (mean + median) / 2 for each component
        - Max error: |centroid(mean) - centroid(median)| / 2
        - is_even flag: whether num_experts is even

        Args:
            arithmetic_mean: The arithmetic mean (Γ) of expert opinions
            median: The statistical median (Ω) of expert opinions
            num_experts: Number of expert opinions (must be >= 1)

        Returns:
            BeCoMeResult instance with all fields calculated

        Raises:
            ValueError: If num_experts < 1

        Example:
            >>> mean = FuzzyTriangleNumber(10.0, 15.0, 20.0)
            >>> median = FuzzyTriangleNumber(12.0, 16.0, 22.0)
            >>> result = BeCoMeResult.from_calculations(mean, median, 5)
            >>> print(result.best_compromise)
            (11.00, 15.50, 21.00)
        """
        if num_experts < 1:
            raise ValueError(f"num_experts must be >= 1, got {num_experts}")

        # Calculate best compromise: (mean + median) / 2 using centralized method
        # Formula from article: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2
        best_compromise = FuzzyTriangleNumber.average([arithmetic_mean, median])

        # Calculate maximum error: |centroid(Γ) - centroid(Ω)| / 2
        mean_centroid = arithmetic_mean.centroid
        median_centroid = median.centroid
        max_error = abs(mean_centroid - median_centroid) / 2

        # Note: is_even is now a computed property, not stored
        return cls(
            best_compromise=best_compromise,
            arithmetic_mean=arithmetic_mean,
            median=median,
            max_error=max_error,
            num_experts=num_experts,
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
