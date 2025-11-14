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


@pytest.fixture
def mean_fuzzy():
    """Fixture providing a fuzzy number representing arithmetic mean.

    :return: FuzzyTriangleNumber(10.0, 15.0, 20.0)
    """
    return FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)


@pytest.fixture
def median_fuzzy():
    """Fixture providing a fuzzy number representing median.

    :return: FuzzyTriangleNumber(12.0, 16.0, 22.0)
    """
    return FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)
