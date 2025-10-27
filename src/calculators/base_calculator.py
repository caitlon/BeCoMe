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
    implementation must provide all four required methods.

    The class enforces the Open/Closed Principle: open for extension
    (new calculator types), closed for modification (interface is stable).
    It also adheres to Interface Segregation Principle by including all
    public methods that are part of the calculator's interface.
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

    @abstractmethod
    def sort_by_centroid(self, opinions: list[ExpertOpinion]) -> list[ExpertOpinion]:
        """
        Sort expert opinions by their centroid values in ascending order.

        This method is part of the public interface and is used by aggregation
        strategies (particularly median calculation) to order opinions.
        Including it in the ABC ensures that all calculator implementations
        provide consistent sorting behavior.

        This demonstrates Interface Segregation Principle (ISP) from SOLID:
        all public methods that clients may use are part of the interface.

        Args:
            opinions: List of expert opinions to sort

        Returns:
            New list of opinions sorted by centroid (ascending order)
            The original list is not modified (immutability principle)

        Example:
            >>> calculator = BeCoMeCalculator()
            >>> opinions = [op1, op2, op3]  # Unordered
            >>> sorted_ops = calculator.sort_by_centroid(opinions)
            >>> # sorted_ops[0] has lowest centroid, sorted_ops[-1] has highest
        """
        pass
