"""Shared pytest fixtures for model tests."""

import pytest

from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def standard_fuzzy():
    """Fixture providing a standard FuzzyTriangleNumber for testing.

    :return: FuzzyTriangleNumber(5.0, 10.0, 15.0)
    """
    return FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)


@pytest.fixture
def equal_values_fuzzy():
    """Fixture providing a FuzzyTriangleNumber where all values are equal.

    :return: FuzzyTriangleNumber(10.0, 10.0, 10.0)
    """
    return FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0)
