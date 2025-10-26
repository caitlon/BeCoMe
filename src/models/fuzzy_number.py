"""
Fuzzy triangular number representation.

This module provides the FuzzyTriangleNumber class for representing
and working with fuzzy triangular numbers in the BeCoMe method.
"""


class FuzzyTriangleNumber:
    """
    Immutable fuzzy triangular number with strict encapsulation.

    A fuzzy triangular number is defined by:
    - lower_bound (A): the minimum possible value
    - peak (C): the most likely value
    - upper_bound (B): the maximum possible value

    Constraint: lower_bound <= peak <= upper_bound

    This class demonstrates strict OOP principles:
    - Encapsulation: All attributes are private (prefixed with _)
    - Immutability: Attributes are read-only via @property decorators
    - Value Object: Instances are compared by value, not identity

    Attributes:
        lower_bound: Minimum value of the fuzzy number (read-only property)
        peak: Most likely value of the fuzzy number (read-only property)
        upper_bound: Maximum value of the fuzzy number (read-only property)
        centroid: Center of gravity of the fuzzy number (computed property)
    """

    __slots__ = ("_lower_bound", "_peak", "_upper_bound")

    def __init__(self, lower_bound: float, peak: float, upper_bound: float) -> None:
        """
        Initialize a fuzzy triangular number with validation.

        Args:
            lower_bound: Minimum value of the fuzzy number
            peak: Most likely value of the fuzzy number
            upper_bound: Maximum value of the fuzzy number

        Raises:
            ValueError: If the constraint lower_bound <= peak <= upper_bound is violated
        """
        if not (lower_bound <= peak <= upper_bound):
            raise ValueError(
                f"Invalid fuzzy triangular number: must satisfy "
                f"lower_bound <= peak <= upper_bound. "
                f"Got: lower_bound={lower_bound}, peak={peak}, "
                f"upper_bound={upper_bound}"
            )

        object.__setattr__(self, "_lower_bound", lower_bound)
        object.__setattr__(self, "_peak", peak)
        object.__setattr__(self, "_upper_bound", upper_bound)

    @property
    def lower_bound(self) -> float:
        """
        Lower bound (minimum value) of the fuzzy triangular number.

        Returns:
            The lower bound value
        """
        return self._lower_bound

    @property
    def peak(self) -> float:
        """
        Peak (most likely value) of the fuzzy triangular number.

        Returns:
            The peak value
        """
        return self._peak

    @property
    def upper_bound(self) -> float:
        """
        Upper bound (maximum value) of the fuzzy triangular number.

        Returns:
            The upper bound value
        """
        return self._upper_bound

    @property
    def centroid(self) -> float:
        """
        Centroid (center of gravity) of the fuzzy triangular number.

        The centroid is the x-coordinate of the center of mass of the triangle,
        calculated as the arithmetic mean of the three characteristic values.

        Formula (from article, equation 9):
            Gx = (A + C + B) / 3

        Returns:
            The centroid value as a float

        Example:
            >>> fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
            >>> fuzzy.centroid
            10.0
        """
        return (self._lower_bound + self._peak + self._upper_bound) / 3.0

    def __setattr__(self, name: str, value: object) -> None:
        """
        Prevent attribute modification to ensure immutability.

        Raises:
            AttributeError: Always, as this object is immutable
        """
        raise AttributeError(f"Cannot modify immutable FuzzyTriangleNumber attribute '{name}'")

    def __delattr__(self, name: str) -> None:
        """
        Prevent attribute deletion to ensure immutability.

        Raises:
            AttributeError: Always, as this object is immutable
        """
        raise AttributeError(f"Cannot delete immutable FuzzyTriangleNumber attribute '{name}'")

    def __eq__(self, other: object) -> bool:
        """
        Compare two fuzzy numbers by value.

        Args:
            other: Another object to compare with

        Returns:
            True if both objects are FuzzyTriangleNumber with same values
        """
        if not isinstance(other, FuzzyTriangleNumber):
            return NotImplemented
        return (
            self._lower_bound == other._lower_bound
            and self._peak == other._peak
            and self._upper_bound == other._upper_bound
        )

    def __hash__(self) -> int:
        """
        Return hash for use in sets and dicts.

        Returns:
            Hash value based on the three characteristic values
        """
        return hash((self._lower_bound, self._peak, self._upper_bound))

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"({self._lower_bound:.2f}, {self._peak:.2f}, {self._upper_bound:.2f})"

    def __repr__(self) -> str:
        """Return technical string representation."""
        return (
            f"FuzzyTriangleNumber(lower_bound={self._lower_bound}, "
            f"peak={self._peak}, upper_bound={self._upper_bound})"
        )
