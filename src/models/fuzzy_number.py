"""
Fuzzy triangular number representation.

This module provides the FuzzyTriangleNumber class for representing
and working with fuzzy triangular numbers in the BeCoMe method.
"""


class FuzzyTriangleNumber:
    """
    Represents a fuzzy triangular number with three characteristic values.

    A fuzzy triangular number is defined by:
    - lower_bound (A): the minimum possible value
    - peak (C): the most likely value
    - upper_bound (B): the maximum possible value

    Constraint: lower_bound <= peak <= upper_bound

    Attributes:
        lower_bound: Minimum value of the fuzzy number
        peak: Most likely value of the fuzzy number
        upper_bound: Maximum value of the fuzzy number
    """

    def __init__(self, lower_bound: float, peak: float, upper_bound: float) -> None:
        """
        Initialize a fuzzy triangular number.

        Args:
            lower_bound: Minimum value (A)
            peak: Most likely value (C)
            upper_bound: Maximum value (B)

        Raises:
            ValueError: If the constraint lower_bound <= peak <= upper_bound is violated
        """
        if not (lower_bound <= peak <= upper_bound):
            raise ValueError(
                f"Invalid fuzzy triangular number: must satisfy "
                f"lower_bound <= peak <= upper_bound. "
                f"Got: lower_bound={lower_bound}, peak={peak}, upper_bound={upper_bound}"
            )

        self.lower_bound: float = lower_bound
        self.peak: float = peak
        self.upper_bound: float = upper_bound

    def __repr__(self) -> str:
        """Return string representation of the fuzzy number."""
        return (
            f"FuzzyTriangleNumber("
            f"lower={self.lower_bound}, "
            f"peak={self.peak}, "
            f"upper={self.upper_bound})"
        )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        return f"({self.lower_bound:.2f}, {self.peak:.2f}, {self.upper_bound:.2f})"

    def get_centroid(self) -> float:
        """
        Calculate the centroid (center of gravity) of the fuzzy triangular number.

        The centroid is the x-coordinate of the center of mass of the triangle,
        calculated as the arithmetic mean of the three characteristic values.

        Formula (from article, equation 9):
            Gx = (A + C + B) / 3

        Returns:
            The centroid value as a float

        Example:
            >>> fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
            >>> fuzzy.get_centroid()
            10.0
        """
        return (self.lower_bound + self.peak + self.upper_bound) / 3.0
