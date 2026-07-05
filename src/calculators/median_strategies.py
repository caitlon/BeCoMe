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

    Different strategies handle odd vs even number of expert opinions. Both
    read the middle of the canonically sorted list by position, so the result
    never depends on the order the opinions arrived in.
    """

    @abstractmethod
    def calculate(self, sorted_opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate median using specific strategy.

        :param sorted_opinions: Expert opinions in canonical order (ascending
            centroid, ties broken by the triangle bounds)
        :return: Median as FuzzyTriangleNumber(rho, omega, sigma)
        """
        pass  # pragma: no cover


class OddMedianStrategy(MedianCalculationStrategy):
    """
    Strategy for calculating median with odd number of experts.

    For odd number (M = 2n + 1), median is the middle opinion
    after sorting by centroid.
    """

    def calculate(self, sorted_opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate median for odd number of experts.

        :param sorted_opinions: Expert opinions in canonical order
        :return: Fuzzy number of the middle expert opinion
        """
        return sorted_opinions[len(sorted_opinions) // 2].opinion


class EvenMedianStrategy(MedianCalculationStrategy):
    """
    Strategy for calculating median with even number of experts.

    For even number (M = 2n), median is the average of the two middle
    opinions after sorting by centroid.

    Formula:
        rho = (A1 + A2) / 2
        omega = (C1 + C2) / 2
        sigma = (B1 + B2) / 2
    """

    def calculate(self, sorted_opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate median for even number of experts.

        Averages the two middle opinions of the sorted list.

        :param sorted_opinions: Expert opinions in canonical order
        :return: Average of the two middle opinions as FuzzyTriangleNumber
        """
        from src.models.fuzzy_number import FuzzyTriangleNumber

        upper_middle = len(sorted_opinions) // 2
        return FuzzyTriangleNumber.average(
            [sorted_opinions[upper_middle - 1].opinion, sorted_opinions[upper_middle].opinion]
        )
