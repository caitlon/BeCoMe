"""
BeCoMe (Best Compromise Mean) calculator.

This module implements the BeCoMe method for aggregating expert opinions
represented as fuzzy triangular numbers, as described in the article by Vrana et al.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF003

from __future__ import annotations

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

        m: int = len(opinions)

        # Calculate sum of each component across all expert opinions
        sum_lower: float = sum(op.opinion.lower_bound for op in opinions)
        sum_peak: float = sum(op.opinion.peak for op in opinions)
        sum_upper: float = sum(op.opinion.upper_bound for op in opinions)

        # Calculate arithmetic mean for each component
        alpha: float = sum_lower / m
        gamma: float = sum_peak / m
        beta: float = sum_upper / m

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

        # Odd number of experts: M = 2n + 1
        if m % 2 == 1:
            # Find middle element
            middle_index: int = m // 2
            middle_opinion = sorted_opinions[middle_index].opinion

            # Median is the middle fuzzy number
            rho: float = middle_opinion.lower_bound
            omega: float = middle_opinion.peak
            sigma: float = middle_opinion.upper_bound

            return FuzzyTriangleNumber(lower_bound=rho, peak=omega, upper_bound=sigma)

        # Even number of experts: M = 2n
        else:
            # Find two middle elements at indices n-1 and n
            n: int = m // 2
            left_index: int = n - 1
            right_index: int = n

            left_opinion = sorted_opinions[left_index].opinion
            right_opinion = sorted_opinions[right_index].opinion

            # Average the two middle fuzzy numbers
            rho = (left_opinion.lower_bound + right_opinion.lower_bound) / 2
            omega = (left_opinion.peak + right_opinion.peak) / 2
            sigma = (left_opinion.upper_bound + right_opinion.upper_bound) / 2

            return FuzzyTriangleNumber(lower_bound=rho, peak=omega, upper_bound=sigma)

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
        delta_max_lower: float = abs(arithmetic_mean.lower_bound - median.lower_bound) / 2
        delta_max_peak: float = abs(arithmetic_mean.peak - median.peak) / 2
        delta_max_upper: float = abs(arithmetic_mean.upper_bound - median.upper_bound) / 2

        max_error: FuzzyTriangleNumber = FuzzyTriangleNumber(
            lower_bound=delta_max_lower, peak=delta_max_peak, upper_bound=delta_max_upper
        )

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
