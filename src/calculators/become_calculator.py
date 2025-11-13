"""BeCoMe (Best Compromise Mean) calculator."""

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

    def _validate_opinions_not_empty(self, opinions: list[ExpertOpinion], operation: str) -> None:
        """
        Validate that opinions list is not empty.

        :param opinions: List of expert opinions to validate
        :param operation: Name of the operation for error message
        :raises EmptyOpinionsError: If opinions list is empty
        """
        if not opinions:
            raise EmptyOpinionsError(f"Cannot calculate {operation} of empty opinions list")

    def calculate_arithmetic_mean(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate arithmetic mean (Gamma) of all expert opinions.

        Formula (equations 3):
            alpha = (1/M) * sum(A_k)  # average of lower bounds
            gamma = (1/M) * sum(C_k)  # average of peaks
            beta = (1/M) * sum(B_k)   # average of upper bounds

        :param opinions: List of expert opinions as fuzzy triangular numbers
        :return: Arithmetic mean as FuzzyTriangleNumber(alpha, gamma, beta)
        :raises EmptyOpinionsError: If opinions list is empty
        """
        self._validate_opinions_not_empty(opinions, "arithmetic mean")

        fuzzy_numbers = [op.opinion for op in opinions]
        return FuzzyTriangleNumber.average(fuzzy_numbers)

    def calculate_median(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate statistical median (Omega) of all expert opinions.

        Median calculation differs based on number of experts:
        - Odd (M = 2n + 1): middle element after sorting by centroid
        - Even (M = 2n): average of two middle elements after sorting

        :param opinions: List of expert opinions as fuzzy triangular numbers
        :return: Median as FuzzyTriangleNumber(rho, omega, sigma)
        :raises EmptyOpinionsError: If opinions list is empty
        """
        self._validate_opinions_not_empty(opinions, "median")

        sorted_opinions: list[ExpertOpinion] = self.sort_by_centroid(opinions)
        m: int = len(sorted_opinions)

        centroids = [op.centroid for op in sorted_opinions]
        median_centroid = statistics.median(centroids)

        strategy: MedianCalculationStrategy = (
            OddMedianStrategy() if m % 2 == 1 else EvenMedianStrategy()
        )

        return strategy.calculate(sorted_opinions, median_centroid)

    def calculate_compromise(self, opinions: list[ExpertOpinion]) -> BeCoMeResult:
        """
        Calculate best compromise (GammaOmegaMean) from expert opinions.

        Combines arithmetic mean (Gamma) and statistical median (Omega)
        to produce best compromise result with maximum error indicator.

        :param opinions: List of expert opinions as fuzzy triangular numbers
        :return: BeCoMeResult containing best compromise and all intermediate results
        :raises EmptyOpinionsError: If opinions list is empty
        """
        self._validate_opinions_not_empty(opinions, "compromise")

        arithmetic_mean: FuzzyTriangleNumber = self.calculate_arithmetic_mean(opinions)
        median: FuzzyTriangleNumber = self.calculate_median(opinions)

        return BeCoMeResult.from_calculations(
            arithmetic_mean=arithmetic_mean,
            median=median,
            num_experts=len(opinions),
        )

    def sort_by_centroid(self, opinions: list[ExpertOpinion]) -> list[ExpertOpinion]:
        """
        Sort expert opinions by centroid values in ascending order.

        Sorting is stable and maintains original order for equal centroids.

        :param opinions: List of expert opinions to sort
        :return: New list of opinions sorted by ascending centroid
        """
        return sorted(opinions, key=lambda op: op.centroid)
