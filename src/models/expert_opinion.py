"""
Expert opinion representation.

This module provides the ExpertOpinion class for representing
an expert's assessment in the BeCoMe method.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fuzzy_number import FuzzyTriangleNumber


@dataclass(frozen=True)
class ExpertOpinion:
    """
    Immutable representation of a single expert's opinion.

    This class uses composition to combine an expert identifier with
    their fuzzy opinion. It supports comparison operations based on
    the centroid of the fuzzy number for sorting purposes.

    The class is immutable (frozen) to ensure value object semantics
    and prevent accidental modification after creation.

    Attributes:
        expert_id: Unique identifier for the expert (e.g., name or ID)
        opinion: The expert's assessment as a FuzzyTriangleNumber
    """

    expert_id: str
    opinion: FuzzyTriangleNumber

    def get_centroid(self) -> float:
        """
        Get the centroid of the expert's opinion.

        This is a convenience method that delegates to the
        FuzzyTriangleNumber's get_centroid method.

        Returns:
            The centroid value of the opinion
        """
        return self.opinion.get_centroid()

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
        return self.get_centroid() < other.get_centroid()

    def __le__(self, other: ExpertOpinion) -> bool:
        """Less than or equal comparison based on centroid."""
        return self.get_centroid() <= other.get_centroid()

    def __eq__(self, other: object) -> bool:
        """
        Equality comparison.

        Two expert opinions are equal if they have the same expert_id
        and the same opinion values.
        """
        if not isinstance(other, ExpertOpinion):
            return NotImplemented
        return (
            self.expert_id == other.expert_id
            and self.opinion.lower_bound == other.opinion.lower_bound
            and self.opinion.peak == other.opinion.peak
            and self.opinion.upper_bound == other.opinion.upper_bound
        )

    def __repr__(self) -> str:
        """Return string representation of the expert opinion."""
        return f"ExpertOpinion(expert_id='{self.expert_id}', opinion={self.opinion})"
