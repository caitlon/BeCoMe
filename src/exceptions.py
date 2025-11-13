"""Custom exceptions for BeCoMe calculations."""


class BeCoMeError(Exception):
    """Base exception for all BeCoMe-related errors."""

    pass


class EmptyOpinionsError(BeCoMeError):
    """Raised when empty list of opinions is provided."""

    pass


class InvalidOpinionError(BeCoMeError):
    """Raised when opinion data is invalid."""

    pass


class CalculationError(BeCoMeError):
    """Raised when calculation fails."""

    pass
