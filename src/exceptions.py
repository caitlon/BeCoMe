"""Custom exceptions for BeCoMe calculations."""


class BeCoMeError(Exception):
    """Base exception for all BeCoMe-related errors."""

    pass


class EmptyOpinionsError(BeCoMeError):
    """Raised when empty list of opinions is provided."""

    pass
