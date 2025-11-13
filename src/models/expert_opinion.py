"""Expert opinion representation."""

from __future__ import annotations

from .fuzzy_number import FuzzyTriangleNumber


class ExpertOpinion:
    """
    Immutable representation of single expert's opinion.

    Combines expert identifier with their fuzzy triangular number opinion.
    Supports comparison operations based on centroid for sorting.

    :ivar expert_id: Unique identifier for the expert (read-only property)
    :ivar opinion: Expert's assessment as FuzzyTriangleNumber (read-only property)
    :ivar centroid: Centroid of the opinion (computed property)
    """

    _expert_id: str
    _opinion: FuzzyTriangleNumber

    __slots__ = ("_expert_id", "_opinion")

    def __init__(self, expert_id: str, opinion: FuzzyTriangleNumber) -> None:
        """
        Initialize expert opinion.

        :param expert_id: Unique identifier for the expert
        :param opinion: Expert's assessment as FuzzyTriangleNumber
        """
        object.__setattr__(self, "_expert_id", expert_id)
        object.__setattr__(self, "_opinion", opinion)

    @property
    def expert_id(self) -> str:
        """
        Unique identifier for the expert.

        :return: Expert's identifier
        """
        return self._expert_id

    @property
    def opinion(self) -> FuzzyTriangleNumber:
        """
        Expert's fuzzy opinion.

        :return: Fuzzy triangular number representing expert's assessment
        """
        return self._opinion

    @property
    def centroid(self) -> float:
        """
        Centroid of the expert's opinion.

        :return: Centroid value of the opinion
        """
        return self._opinion.centroid

    def __setattr__(self, name: str, value: object) -> None:
        """
        Prevent attribute modification to ensure immutability.

        :raises AttributeError: Always, as object is immutable
        """
        raise AttributeError(f"Cannot modify immutable ExpertOpinion attribute '{name}'")

    def __delattr__(self, name: str) -> None:
        """
        Prevent attribute deletion to ensure immutability.

        :raises AttributeError: Always, as object is immutable
        """
        raise AttributeError(f"Cannot delete immutable ExpertOpinion attribute '{name}'")

    def __lt__(self, other: ExpertOpinion) -> bool:
        """
        Compare expert opinions based on centroids.

        :param other: Another ExpertOpinion to compare with
        :return: True if this opinion's centroid is less than the other's
        """
        return self.centroid < other.centroid

    def __le__(self, other: ExpertOpinion) -> bool:
        """Less than or equal comparison based on centroid."""
        return self.centroid <= other.centroid

    def __eq__(self, other: object) -> bool:
        """
        Equality comparison.

        :param other: Another object to compare with
        :return: True if both are ExpertOpinion with same expert_id and opinion
        """
        if not isinstance(other, ExpertOpinion):
            return False
        return self._expert_id == other._expert_id and self._opinion == other._opinion

    def __hash__(self) -> int:
        """
        Return hash for use in sets and dicts.

        :return: Hash value based on expert_id and opinion
        """
        return hash((self._expert_id, self._opinion))

    def __repr__(self) -> str:
        """Return string representation of the expert opinion."""
        return f"ExpertOpinion(expert_id='{self._expert_id}', opinion={self._opinion})"

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"{self._expert_id}: {self._opinion}"
