"""
BeCoMe (Best Compromise Mean) calculator.

This module implements the BeCoMe method for aggregating expert opinions
represented as fuzzy triangular numbers, as described in the article by Vrana et al.
"""

# ignore ruff rule for mathematical symbols
from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.median_strategies import (
    EvenMedianStrategy,
    MedianCalculationStrategy,
    OddMedianStrategy,
)
from src.exceptions import EmptyOpinionsError
from src.models.become_result import BeCoMeResult
from src.models.fuzzy_number import FuzzyTriangleNumber

if TYPE_CHECKING:
    from src.models.expert_opinion import ExpertOpinion


class BeCoMeCalculator(BaseAggregationCalculator):
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
            EmptyOpinionsError: If opinions list is empty
        """
        if not opinions:
            raise EmptyOpinionsError("Cannot calculate arithmetic mean of empty opinions list")

        # Calculate arithmetic mean for each component
        alpha: float = statistics.mean(op.opinion.lower_bound for op in opinions)
        gamma: float = statistics.mean(op.opinion.peak for op in opinions)
        beta: float = statistics.mean(op.opinion.upper_bound for op in opinions)

        return FuzzyTriangleNumber(lower_bound=alpha, peak=gamma, upper_bound=beta)

    def calculate_median(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate the statistical median (Omega) of all expert opinions.

        This method uses the Strategy Pattern to delegate the actual median
        calculation to either OddMedianStrategy or EvenMedianStrategy,
        depending on the number of expert opinions. This demonstrates the
        Open/Closed Principle (OCP) from SOLID - the method is closed for
        modification but open for extension through strategies.

        The median is calculated differently for odd and even number of experts:
        - Odd (M = 2n + 1): middle element after sorting by centroid
        - Even (M = 2n): average of two middle elements after sorting

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            Median as FuzzyTriangleNumber(rho, omega, sigma)

        Raises:
            EmptyOpinionsError: If opinions list is empty
        """
        if not opinions:
            raise EmptyOpinionsError("Cannot calculate median of empty opinions list")

        # Sort opinions by centroid
        sorted_opinions: list[ExpertOpinion] = self.sort_by_centroid(opinions)
        m: int = len(sorted_opinions)

        # Calculate median centroid for strategy
        centroids = [op.centroid for op in sorted_opinions]
        median_centroid = statistics.median(centroids)

        # Strategy Pattern: select strategy based on number of experts
        # This eliminates if-else logic and adheres to OCP
        strategy: MedianCalculationStrategy = (
            OddMedianStrategy() if m % 2 == 1 else EvenMedianStrategy()
        )

        return strategy.calculate(sorted_opinions, median_centroid)

    def calculate_compromise(self, opinions: list[ExpertOpinion]) -> BeCoMeResult:
        """
        Calculate the best compromise (GammaOmegaMean) from expert opinions.

        This is the main method that:
        1. Calculates arithmetic mean (Gamma)
        2. Calculates statistical median (Omega)
        3. Uses factory method to create result with best compromise and error

        The calculation logic for best compromise and max error is encapsulated
        in BeCoMeResult.from_calculations() factory method, demonstrating the
        Factory Method pattern for clean separation of concerns.

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            BeCoMeResult containing best compromise and all intermediate results

        Raises:
            EmptyOpinionsError: If opinions list is empty
        """
        if not opinions:
            raise EmptyOpinionsError("Cannot calculate compromise of empty opinions list")

        # Step 1: Calculate arithmetic mean (Gamma)
        arithmetic_mean: FuzzyTriangleNumber = self.calculate_arithmetic_mean(opinions)

        # Step 2: Calculate statistical median (Omega)
        median: FuzzyTriangleNumber = self.calculate_median(opinions)

        # Step 3: Use factory method to create result
        # The factory encapsulates the logic for:
        # - Best compromise calculation: (Gamma + Omega) / 2
        # - Maximum error calculation: |Gamma - Omega| / 2
        # - is_even flag determination
        return BeCoMeResult.from_calculations(
            arithmetic_mean=arithmetic_mean,
            median=median,
            num_experts=len(opinions),
        )

    def sort_by_centroid(self, opinions: list[ExpertOpinion]) -> list[ExpertOpinion]:
        """
        Sort expert opinions by their centroid values.

        This is a public method that can be used for sorting opinions by centroid,
        primarily used internally for median calculation but available for analysis.
        Sorting is stable and maintains original order for equal centroids.

        Args:
            opinions: List of expert opinions to sort

        Returns:
            Sorted list of expert opinions (by ascending centroid)
        """
        return sorted(opinions, key=lambda op: op.centroid)
