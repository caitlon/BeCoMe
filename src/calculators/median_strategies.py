"""Median calculation strategies for BeCoMe method."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.expert_opinion import ExpertOpinion
    from src.models.fuzzy_number import FuzzyTriangleNumber


class MedianCalculationStrategy(ABC):
    """
    Abstract base class for median calculation strategies.

    Different strategies handle odd vs even number of expert opinions.
    """

    @staticmethod
    def _find_closest_opinion(
        opinions: list[ExpertOpinion],
        target_centroid: float,
    ) -> ExpertOpinion:
        """
        Find opinion with centroid closest to target centroid.

        :param opinions: List of expert opinions to search
        :param target_centroid: Target centroid value to match
        :return: ExpertOpinion with centroid closest to target
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

        :param sorted_opinions: Expert opinions sorted by centroid (ascending)
        :param median_centroid: Median centroid value
        :return: Median as FuzzyTriangleNumber(rho, omega, sigma)
        """
        pass  # pragma: no cover


class OddMedianStrategy(MedianCalculationStrategy):
    """
    Strategy for calculating median with odd number of experts.

    For odd number (M = 2n + 1), median is the middle opinion
    after sorting by centroid.
    """

    def calculate(
        self,
        sorted_opinions: list[ExpertOpinion],
        median_centroid: float,
    ) -> FuzzyTriangleNumber:
        """
        Calculate median for odd number of experts.

        :param sorted_opinions: Expert opinions sorted by centroid
        :param median_centroid: Median centroid value
        :return: Fuzzy number of the middle expert opinion
        """
        median_opinion = self._find_closest_opinion(sorted_opinions, median_centroid)

        return median_opinion.opinion


class EvenMedianStrategy(MedianCalculationStrategy):
    """
    Strategy for calculating median with even number of experts.

    For even number (M = 2n), median is the average of the two middle
    opinions after sorting by centroid.
    """

    def calculate(
        self,
        sorted_opinions: list[ExpertOpinion],
        median_centroid: float,
    ) -> FuzzyTriangleNumber:
        """
        Calculate median for even number of experts.

        Averages the two middle opinions (those closest to median centroid).

        Formula:
            rho = (A1 + A2) / 2
            omega = (C1 + C2) / 2
            sigma = (B1 + B2) / 2

        :param sorted_opinions: Expert opinions sorted by centroid
        :param median_centroid: Median centroid value
        :return: Average of the two middle opinions as FuzzyTriangleNumber
        """
        from src.models.fuzzy_number import FuzzyTriangleNumber

        first_median_opinion = self._find_closest_opinion(sorted_opinions, median_centroid)

        remaining_opinions = [op for op in sorted_opinions if op != first_median_opinion]
        second_median_opinion = self._find_closest_opinion(remaining_opinions, median_centroid)

        return FuzzyTriangleNumber.average(
            [first_median_opinion.opinion, second_median_opinion.opinion]
        )
