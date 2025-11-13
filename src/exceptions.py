"""
Custom exceptions for BeCoMe calculations.

This module provides a hierarchy of domain-specific exceptions
for clear error handling in BeCoMe method calculations.
"""


class BeCoMeError(Exception):
    """Base exception for all BeCoMe-related errors."""

    pass


class EmptyOpinionsError(BeCoMeError):
    """Raised when an empty list of opinions is provided to a calculation."""

    pass


class InvalidOpinionError(BeCoMeError):
    """Raised when opinion data is invalid or malformed."""

    pass


class CalculationError(BeCoMeError):
    """Raised when a calculation cannot be completed."""

    pass
