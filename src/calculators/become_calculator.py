"""
BeCoMe (Best Compromise Mean) calculator.

This module implements the BeCoMe method for aggregating expert opinions
represented as fuzzy triangular numbers, as described in the article by Vrana et al.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from src.models.become_result import BeCoMeResult
from src.models.fuzzy_number import FuzzyTriangleNumber

if TYPE_CHECKING:
    from src.models.expert_opinion import ExpertOpinion


class BeCoMeCalculator:
    """
    Calculator for the BeCoMe (Best Compromise Mean) method.

    The BeCoMe method combines arithmetic mean (Gamma) and statistical median (Omega)
    of expert opinions to produce a best compromise result (GammaOmegaMean).

    Key formulas:
        - Arithmetic mean: Gamma(alpha, gamma, beta)
        - Statistical median: Omega(rho, omega, sigma)
        - Best compromise: GammaOmegaMean(pi, phi, xi) = (Gamma + Omega) / 2
    """

    def calculate_arithmetic_mean(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate the arithmetic mean (Gamma) of all expert opinions.

        Formula from article (equations 3):
            alpha = (1/M) * sum(A_k)  # average of lower bounds
            gamma = (1/M) * sum(C_k)  # average of peaks
            beta = (1/M) * sum(B_k)   # average of upper bounds

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            Arithmetic mean as FuzzyTriangleNumber(alpha, gamma, beta)

        Raises:
            ValueError: If opinions list is empty
        """
        if not opinions:
            raise ValueError("Cannot calculate arithmetic mean of empty opinions list")

        # Calculate arithmetic mean for each component
        alpha: float = statistics.mean(op.opinion.lower_bound for op in opinions)
        gamma: float = statistics.mean(op.opinion.peak for op in opinions)
        beta: float = statistics.mean(op.opinion.upper_bound for op in opinions)

        return FuzzyTriangleNumber(lower_bound=alpha, peak=gamma, upper_bound=beta)

    def calculate_median(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate the statistical median (Omega) of all expert opinions.

        The median is calculated differently for odd and even number of experts:
        - Odd (M = 2n + 1): middle element after sorting by centroid
        - Even (M = 2n): average of two middle elements after sorting

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            Median as FuzzyTriangleNumber(rho, omega, sigma)

        Raises:
            ValueError: If opinions list is empty
        """
        if not opinions:
            raise ValueError("Cannot calculate median of empty opinions list")

        # Sort opinions by centroid
        sorted_opinions: list[ExpertOpinion] = self._sort_by_centroid(opinions)
        m: int = len(sorted_opinions)

        # Use statistics.median for centroid values
        centroids = [op.get_centroid() for op in sorted_opinions]
        median_centroid = statistics.median(centroids)

        # Find the opinion with median centroid
        median_opinion = min(
            sorted_opinions, key=lambda op: abs(op.get_centroid() - median_centroid)
        )

        # For even number of experts, average with the next closest opinion
        if m % 2 == 0:
            # Find the second closest opinion to median centroid
            remaining_opinions = [op for op in sorted_opinions if op != median_opinion]
            second_median_opinion = min(
                remaining_opinions, key=lambda op: abs(op.get_centroid() - median_centroid)
            )

            # Average the two median opinions
            rho = (
                median_opinion.opinion.lower_bound + second_median_opinion.opinion.lower_bound
            ) / 2
            omega = (median_opinion.opinion.peak + second_median_opinion.opinion.peak) / 2
            sigma = (
                median_opinion.opinion.upper_bound + second_median_opinion.opinion.upper_bound
            ) / 2

            return FuzzyTriangleNumber(lower_bound=rho, peak=omega, upper_bound=sigma)
        else:
            # For odd number, use the median opinion directly
            return median_opinion.opinion

    def calculate_compromise(self, opinions: list[ExpertOpinion]) -> BeCoMeResult:
        """
        Calculate the best compromise (GammaOmegaMean) from expert opinions.

        This is the main method that:
        1. Calculates arithmetic mean (Gamma)
        2. Calculates statistical median (Omega)
        3. Computes best compromise: (Gamma + Omega) / 2
        4. Calculates maximum error: |Gamma - Omega| / 2

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            BeCoMeResult containing best compromise and all intermediate results

        Raises:
            ValueError: If opinions list is empty
        """
        if not opinions:
            raise ValueError("Cannot calculate compromise of empty opinions list")

        # Step 1: Calculate arithmetic mean (Gamma)
        arithmetic_mean: FuzzyTriangleNumber = self.calculate_arithmetic_mean(opinions)

        # Step 2: Calculate statistical median (Omega)
        median: FuzzyTriangleNumber = self.calculate_median(opinions)

        # Step 3: Calculate best compromise (ΓΩMean)
        # Formula from article (equations 11): π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2
        pi: float = (arithmetic_mean.lower_bound + median.lower_bound) / 2
        phi: float = (arithmetic_mean.peak + median.peak) / 2
        xi: float = (arithmetic_mean.upper_bound + median.upper_bound) / 2

        best_compromise: FuzzyTriangleNumber = FuzzyTriangleNumber(
            lower_bound=pi, peak=phi, upper_bound=xi
        )

        # Step 4: Calculate maximum error (Δmax)
        # Formula from article (equation 12): Δmax = |Γ - Ω| / 2
        # This is the distance between centroids of arithmetic mean and median
        mean_centroid: float = arithmetic_mean.get_centroid()
        median_centroid: float = median.get_centroid()
        max_error: float = abs(mean_centroid - median_centroid) / 2

        # Step 5: Create and return result
        m: int = len(opinions)
        is_even: bool = m % 2 == 0

        return BeCoMeResult(
            best_compromise=best_compromise,
            arithmetic_mean=arithmetic_mean,
            median=median,
            max_error=max_error,
            num_experts=m,
            is_even=is_even,
        )

    def _sort_by_centroid(self, opinions: list[ExpertOpinion]) -> list[ExpertOpinion]:
        """
        Sort expert opinions by their centroid values.

        This is a helper method used for median calculation.
        Sorting is stable and maintains original order for equal centroids.

        Args:
            opinions: List of expert opinions to sort

        Returns:
            Sorted list of expert opinions (by ascending centroid)
        """
        return sorted(opinions, key=lambda op: op.get_centroid())
