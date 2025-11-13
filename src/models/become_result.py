"""BeCoMe calculation result representation."""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001, RUF003

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .fuzzy_number import FuzzyTriangleNumber


class BeCoMeResult(BaseModel):
    """
    Immutable result of BeCoMe calculation.

    Stores best compromise, arithmetic mean, median, and error metrics.

    :ivar best_compromise: Final result (ΓΩMean) - average of mean and median
    :ivar arithmetic_mean: Arithmetic mean (Γ) of expert opinions
    :ivar median: Statistical median (Ω) of expert opinions
    :ivar max_error: Maximum error (Δmax) between mean and median centroids
    :ivar num_experts: Number of expert opinions
    :ivar is_even: Whether number of experts is even (computed property)
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

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_even(self) -> bool:
        """
        Check if number of experts is even.

        :return: True if number of experts is even, False if odd
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
        Create BeCoMeResult from mean and median calculations.

        Calculates best compromise and maximum error automatically.

        :param arithmetic_mean: Arithmetic mean (Γ) of expert opinions
        :param median: Statistical median (Ω) of expert opinions
        :param num_experts: Number of expert opinions (must be >= 1)
        :return: BeCoMeResult instance with all fields calculated
        :raises ValueError: If num_experts < 1
        """
        if num_experts < 1:
            raise ValueError(f"num_experts must be >= 1, got {num_experts}")

        best_compromise = FuzzyTriangleNumber.average([arithmetic_mean, median])

        mean_centroid = arithmetic_mean.centroid
        median_centroid = median.centroid
        max_error = abs(mean_centroid - median_centroid) / 2

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
