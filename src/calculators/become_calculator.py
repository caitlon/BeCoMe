"""
BeCoMe (Best Compromise Mean) calculator.

This module implements the BeCoMe method for aggregating expert opinions
represented as fuzzy triangular numbers, as described in the article by Vrana et al.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.expert_opinion import ExpertOpinion
    from src.models.fuzzy_number import FuzzyTriangleNumber


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

    def calculate_arithmetic_mean(
        self, opinions: list[ExpertOpinion]
    ) -> FuzzyTriangleNumber:
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
        raise NotImplementedError("Arithmetic mean calculation not yet implemented")

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
        raise NotImplementedError("Median calculation not yet implemented")

    def calculate_compromise(
        self, opinions: list[ExpertOpinion]
    ) -> "BeCoMeResult":  # type: ignore
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
        raise NotImplementedError("Compromise calculation not yet implemented")

    def _sort_by_centroid(
        self, opinions: list[ExpertOpinion]
    ) -> list[ExpertOpinion]:
        """
        Sort expert opinions by their centroid values.

        This is a helper method used for median calculation.
        Sorting is stable and maintains original order for equal centroids.

        Args:
            opinions: List of expert opinions to sort

        Returns:
            Sorted list of expert opinions (by ascending centroid)
        """
        raise NotImplementedError("Sorting by centroid not yet implemented")

