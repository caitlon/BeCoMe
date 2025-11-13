"""Abstract base class for expert opinion aggregation calculators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.become_result import BeCoMeResult
    from src.models.expert_opinion import ExpertOpinion
    from src.models.fuzzy_number import FuzzyTriangleNumber


class BaseAggregationCalculator(ABC):
    """
    Abstract base class for expert opinion aggregation calculators.

    Defines interface for calculators that aggregate expert opinions
    represented as fuzzy triangular numbers.
    """

    @abstractmethod
    def calculate_arithmetic_mean(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate arithmetic mean of expert opinions.

        :param opinions: List of expert opinions as fuzzy triangular numbers
        :return: Arithmetic mean as FuzzyTriangleNumber
        :raises EmptyOpinionsError: If opinions list is empty
        """
        pass  # pragma: no cover

    @abstractmethod
    def calculate_median(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate statistical median of expert opinions.

        :param opinions: List of expert opinions as fuzzy triangular numbers
        :return: Median as FuzzyTriangleNumber
        :raises EmptyOpinionsError: If opinions list is empty
        """
        pass  # pragma: no cover

    @abstractmethod
    def calculate_compromise(self, opinions: list[ExpertOpinion]) -> BeCoMeResult:
        """
        Calculate best compromise from expert opinions.

        :param opinions: List of expert opinions as fuzzy triangular numbers
        :return: Complete calculation result with compromise and metadata
        :raises EmptyOpinionsError: If opinions list is empty
        """
        pass  # pragma: no cover

    @abstractmethod
    def sort_by_centroid(self, opinions: list[ExpertOpinion]) -> list[ExpertOpinion]:
        """
        Sort expert opinions by centroid values in ascending order.

        :param opinions: List of expert opinions to sort
        :return: New list of opinions sorted by centroid (original list unchanged)
        """
        pass  # pragma: no cover
