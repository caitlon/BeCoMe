"""
Abstract base class for expert opinion aggregation calculators.

This module defines the contract that all aggregation calculators
must implement, ensuring polymorphic behavior and extensibility.
"""

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

    This class defines the contract for all calculators that aggregate
    expert opinions represented as fuzzy triangular numbers. Any concrete
    implementation must provide all three calculation methods.

    The class enforces the Open/Closed Principle: open for extension
    (new calculator types), closed for modification (interface is stable).
    """

    @abstractmethod
    def calculate_arithmetic_mean(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate the arithmetic mean of expert opinions.

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            Arithmetic mean as a FuzzyTriangleNumber

        Raises:
            EmptyOpinionsError: If opinions list is empty
        """
        pass

    @abstractmethod
    def calculate_median(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """
        Calculate the statistical median of expert opinions.

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            Median as a FuzzyTriangleNumber

        Raises:
            EmptyOpinionsError: If opinions list is empty
        """
        pass

    @abstractmethod
    def calculate_compromise(self, opinions: list[ExpertOpinion]) -> BeCoMeResult:
        """
        Calculate the best compromise from expert opinions.

        This is the main method that combines different aggregation
        strategies to produce a final result.

        Args:
            opinions: List of expert opinions as fuzzy triangular numbers

        Returns:
            Complete calculation result with compromise and metadata

        Raises:
            EmptyOpinionsError: If opinions list is empty
        """
        pass
