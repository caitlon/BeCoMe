"""
Calculators for the BeCoMe method.

This module contains calculators for computing the Best Compromise Mean
from expert opinions represented as fuzzy triangular numbers.
"""

from .base_calculator import BaseAggregationCalculator
from .become_calculator import BeCoMeCalculator
from .median_strategies import (
    EvenMedianStrategy,
    MedianCalculationStrategy,
    OddMedianStrategy,
)

__all__ = [
    "BaseAggregationCalculator",
    "BeCoMeCalculator",
    "MedianCalculationStrategy",
    "OddMedianStrategy",
    "EvenMedianStrategy",
]
