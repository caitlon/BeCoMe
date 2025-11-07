"""
Median calculation strategies for BeCoMe method.

This module implements the Strategy Pattern for calculating median
of expert opinions, eliminating if-else logic and adhering to the
Open/Closed Principle (OCP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.expert_opinion import ExpertOpinion
    from src.models.fuzzy_number import FuzzyTriangleNumber


class MedianCalculationStrategy(ABC):
    """
    Abstract base class for median calculation strategies.

    This class defines the contract for all median calculation strategies,
    ensuring they implement the calculate() method. This demonstrates the
    Strategy Pattern and Open/Closed Principle from SOLID.

    Different strategies are used based on whether the number of expert
    opinions is odd or even, as the median calculation differs.
    """

    @staticmethod
    def _find_closest_opinion(
        opinions: list[ExpertOpinion],
        target_centroid: float,
    ) -> ExpertOpinion:
        """
        Find the opinion with centroid closest to the target centroid.

        This is a static helper method used by median calculation strategies
        to locate the expert opinion(s) whose centroid is nearest to the
        median centroid value. It's a static method because it doesn't depend
        on instance state and is logically part of the median calculation
        strategy family.

        Args:
            opinions: List of expert opinions to search
            target_centroid: Target centroid value to match

        Returns:
            ExpertOpinion with centroid closest to target_centroid

        Example:
            >>> opinions = [op1, op2, op3]  # centroids: 5.0, 8.0, 12.0
            >>> target = 7.5
            >>> closest = MedianCalculationStrategy._find_closest_opinion(opinions, target)
            >>> # Returns op2 (centroid 8.0 is closest to 7.5)
        """
        return min(opinions, key=lambda op: abs(op.centroid - target_centroid))

    @abstractmethod
    def calculate(
        self,
        sorted_opinions: list[ExpertOpinion],
        median_centroid: float,
    ) -> FuzzyTriangleNumber:
        """
        Calculate median using specific strategy.

        Args:
            sorted_opinions: Expert opinions sorted by centroid (ascending)
            median_centroid: The median centroid value (from statistics.median)

        Returns:
            Median as FuzzyTriangleNumber(rho, omega, sigma)
        """
        pass


class OddMedianStrategy(MedianCalculationStrategy):
    """
    Strategy for calculating median with odd number of experts.

    For odd number of experts (M = 2n + 1), the median is simply
    the middle opinion after sorting by centroid. This is the opinion
    whose centroid is closest to the median centroid value.

    This class demonstrates Single Responsibility Principle (SRP) by
    handling only the odd-case median calculation logic.
    """

    def calculate(
        self,
        sorted_opinions: list[ExpertOpinion],
        median_centroid: float,
    ) -> FuzzyTriangleNumber:
        """
        Calculate median for odd number of experts.

        For odd number, return the middle opinion directly. This is the
        opinion with centroid closest to the median centroid value.

        Args:
            sorted_opinions: Expert opinions sorted by centroid
            median_centroid: The median centroid value

        Returns:
            The fuzzy number of the middle expert opinion

        Example:
            >>> # With 5 experts, return the 3rd opinion (middle)
            >>> sorted_ops = [op1, op2, op3, op4, op5]
            >>> strategy = OddMedianStrategy()
            >>> median = strategy.calculate(sorted_ops, median_centroid)
            >>> # median will be op3.opinion
        """
        # Find the opinion with median centroid using static helper method
        median_opinion = self._find_closest_opinion(sorted_opinions, median_centroid)

        return median_opinion.opinion


class EvenMedianStrategy(MedianCalculationStrategy):
    """
    Strategy for calculating median with even number of experts.

    For even number of experts (M = 2n), the median is the average
    of the two middle opinions after sorting by centroid. This involves
    finding the two opinions whose centroids are closest to the median
    centroid value and averaging their fuzzy number components.

    This class demonstrates Single Responsibility Principle (SRP) by
    handling only the even-case median calculation logic.
    """

    def calculate(
        self,
        sorted_opinions: list[ExpertOpinion],
        median_centroid: float,
    ) -> FuzzyTriangleNumber:
        """
        Calculate median for even number of experts.

        For even number, average the two middle opinions. These are the
        two opinions with centroids closest to the median centroid value.

        Formula:
            rho = (A1 + A2) / 2    # average of lower bounds
            omega = (C1 + C2) / 2  # average of peaks
            sigma = (B1 + B2) / 2  # average of upper bounds

        Args:
            sorted_opinions: Expert opinions sorted by centroid
            median_centroid: The median centroid value

        Returns:
            Average of the two middle opinions as FuzzyTriangleNumber

        Example:
            >>> # With 4 experts, average 2nd and 3rd opinions
            >>> sorted_ops = [op1, op2, op3, op4]
            >>> strategy = EvenMedianStrategy()
            >>> median = strategy.calculate(sorted_ops, median_centroid)
            >>> # median will be average of op2.opinion and op3.opinion
        """
        from src.models.fuzzy_number import FuzzyTriangleNumber

        # Find the first opinion with median centroid using static helper method
        first_median_opinion = self._find_closest_opinion(sorted_opinions, median_centroid)

        # Find the second closest opinion to median centroid
        remaining_opinions = [op for op in sorted_opinions if op != first_median_opinion]
        second_median_opinion = self._find_closest_opinion(remaining_opinions, median_centroid)

        # Average the two median opinions using centralized method
        return FuzzyTriangleNumber.average(
            [first_median_opinion.opinion, second_median_opinion.opinion]
        )
