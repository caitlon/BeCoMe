"""
Shared pytest fixtures for model tests.

This module provides common fixtures used across multiple test files,
following the DRY principle and pytest best practices from Lott's book.
"""

import pytest

from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def standard_fuzzy():
    """Fixture providing a standard FuzzyTriangleNumber for testing.

    Returns a fuzzy triangular number with values (5.0, 10.0, 15.0).
    This is the most commonly used fuzzy number across model tests.

    This fixture implements the GIVEN step by preparing test data
    that can be injected into any test via Dependency Injection.
    """
    return FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)


@pytest.fixture
def equal_values_fuzzy():
    """Fixture providing a FuzzyTriangleNumber where all values are equal.

    Returns a fuzzy triangular number with values (10.0, 10.0, 10.0).
    Useful for testing edge cases and special behaviors.
    """
    return FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0)


@pytest.fixture
def mean_fuzzy():
    """Fixture providing a fuzzy number representing arithmetic mean.

    Returns FuzzyTriangleNumber(10.0, 15.0, 20.0).
    Commonly used in BeCoMeResult factory method tests.
    """
    return FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)


@pytest.fixture
def median_fuzzy():
    """Fixture providing a fuzzy number representing median.

    Returns FuzzyTriangleNumber(12.0, 16.0, 22.0).
    Commonly used in BeCoMeResult factory method tests.
    """
    return FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)
