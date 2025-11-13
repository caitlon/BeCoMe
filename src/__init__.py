"""BeCoMe (Best Compromise Mean) method for group decision-making."""

from .exceptions import (
    BeCoMeError,
    CalculationError,
    EmptyOpinionsError,
    InvalidOpinionError,
)

__version__ = "0.1.0"

__all__ = [
    "BeCoMeError",
    "CalculationError",
    "EmptyOpinionsError",
    "InvalidOpinionError",
]
