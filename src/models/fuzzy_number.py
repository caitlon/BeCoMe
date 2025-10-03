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
        """
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
        return f"({self.lower_bound}, {self.peak}, {self.upper_bound})"
