"""
Expert opinion representation.

This module provides the ExpertOpinion class for representing
an expert's assessment in the BeCoMe method.
"""

from __future__ import annotations

from .fuzzy_number import FuzzyTriangleNumber


class ExpertOpinion:
    """
    Immutable representation of a single expert's opinion with strict encapsulation.

    This class uses composition to combine an expert identifier with
    their fuzzy opinion. It supports comparison operations based on
    the centroid of the fuzzy number for sorting purposes.

    This class demonstrates strict OOP principles:
    - Encapsulation: All attributes are private (prefixed with _)
    - Immutability: Attributes are read-only via @property decorators
    - Composition: Contains a FuzzyTriangleNumber (has-a relationship)
    - Value Object: Compared by value, not identity

    Attributes:
        expert_id: Unique identifier for the expert (read-only property)
        opinion: The expert's assessment as a FuzzyTriangleNumber (read-only property)
        centroid: Centroid of the expert's opinion (computed property)
    """

    _expert_id: str
    _opinion: FuzzyTriangleNumber

    __slots__ = ("_expert_id", "_opinion")

    def __init__(self, expert_id: str, opinion: FuzzyTriangleNumber) -> None:
        """
        Initialize an expert opinion.

        Args:
            expert_id: Unique identifier for the expert (e.g., name or ID)
            opinion: The expert's assessment as a FuzzyTriangleNumber
        """
        object.__setattr__(self, "_expert_id", expert_id)
        object.__setattr__(self, "_opinion", opinion)

    @property
    def expert_id(self) -> str:
        """
        Unique identifier for the expert.

        Returns:
            The expert's identifier
        """
        return self._expert_id

    @property
    def opinion(self) -> FuzzyTriangleNumber:
        """
        The expert's fuzzy opinion.

        Returns:
            The fuzzy triangular number representing the expert's assessment
        """
        return self._opinion

    @property
    def centroid(self) -> float:
        """
        Centroid (center of gravity) of the expert's opinion.

        This property delegates to the FuzzyTriangleNumber's centroid property,
        providing convenient access to the centroid value.

        Returns:
            The centroid value of the opinion

        Example:
            >>> opinion = ExpertOpinion("E1", FuzzyTriangleNumber(5.0, 10.0, 15.0))
            >>> opinion.centroid
            10.0
        """
        return self._opinion.centroid

    def __setattr__(self, name: str, value: object) -> None:
        """
        Prevent attribute modification to ensure immutability.

        Raises:
            AttributeError: Always, as this object is immutable
        """
        raise AttributeError(f"Cannot modify immutable ExpertOpinion attribute '{name}'")

    def __delattr__(self, name: str) -> None:
        """
        Prevent attribute deletion to ensure immutability.

        Raises:
            AttributeError: Always, as this object is immutable
        """
        raise AttributeError(f"Cannot delete immutable ExpertOpinion attribute '{name}'")

    def __lt__(self, other: ExpertOpinion) -> bool:
        """
        Compare two expert opinions based on their centroids.

        This enables sorting of expert opinions by their centroid values,
        which is required for median calculation in the BeCoMe method.

        Args:
            other: Another ExpertOpinion to compare with

        Returns:
            True if this opinion's centroid is less than the other's
        """
        return self.centroid < other.centroid

    def __le__(self, other: ExpertOpinion) -> bool:
        """Less than or equal comparison based on centroid."""
        return self.centroid <= other.centroid

    def __eq__(self, other: object) -> bool:
        """
        Equality comparison.

        Two expert opinions are equal if they have the same expert_id
        and the same opinion values.

        Args:
            other: Another object to compare with

        Returns:
            True if both objects are ExpertOpinion with same values
        """
        if not isinstance(other, ExpertOpinion):
            return False
        return self._expert_id == other._expert_id and self._opinion == other._opinion

    def __hash__(self) -> int:
        """
        Return hash for use in sets and dicts.

        Returns:
            Hash value based on expert_id and opinion
        """
        return hash((self._expert_id, self._opinion))

    def __repr__(self) -> str:
        """Return string representation of the expert opinion."""
        return f"ExpertOpinion(expert_id='{self._expert_id}', opinion={self._opinion})"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self._expert_id}: {self._opinion}"
