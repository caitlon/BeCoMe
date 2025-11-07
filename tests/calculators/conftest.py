"""
Shared fixtures for calculator tests.

- Fixtures provide test data and setup (GIVEN phase)
- scope parameter optimizes resource usage
- Fixtures enable Dependency Injection in tests
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture(scope="class")
def calculator():
    """
    Provide a BeCoMeCalculator instance for all tests in a class.

    Using scope="class" as recommended by Lott: creates the calculator
    once per test class, reducing object creation overhead.
    """
    return BeCoMeCalculator()


@pytest.fixture
def three_experts_opinions():
    """Provide opinions from 3 experts with sequential values."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
        ),
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def single_expert_opinion():
    """Provide opinion from a single expert."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def two_experts_decimal_opinions():
    """Provide opinions from 2 experts with decimal values."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=2.5, peak=5.5, upper_bound=8.5),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=3.5, peak=6.5, upper_bound=9.5),
        ),
    ]


@pytest.fixture
def two_experts_independent_components():
    """Provide opinions to test component independence."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=10.0, upper_bound=10.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=20.0, peak=30.0, upper_bound=40.0),
        ),
    ]
