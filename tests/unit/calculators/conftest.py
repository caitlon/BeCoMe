"""
Shared fixtures for calculator tests.

Following pytest best practices:
- Only fixtures shared across MULTIPLE test modules are here
- Single-use fixtures are defined in their respective test files
- Fixtures provide test data (GIVEN phase)
- scope parameter optimizes resource usage
- Fixtures enable Dependency Injection in tests
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Core fixtures used across all test files


@pytest.fixture(scope="class")
def calculator():
    """
    Provide a BeCoMeCalculator instance for all tests in a class.

    Using scope="class" as recommended by Lott: creates the calculator
    once per test class, reducing object creation overhead.

    Used in: test_arithmetic_mean, test_median, test_compromise,
             test_median_strategies, test_base_calculator
    """
    return BeCoMeCalculator()


@pytest.fixture
def three_experts_opinions():
    """
    Provide opinions from 3 experts with sequential values.

    Used in: test_arithmetic_mean, test_median, test_compromise
    """
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
    """
    Provide opinion from a single expert.

    Used in: test_arithmetic_mean, test_median, test_compromise
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def four_experts_even_opinions():
    """
    Provide opinions from 4 experts (even number).

    Used in: test_median, test_compromise
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
        ),
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=8.0, upper_bound=9.0),
        ),
        ExpertOpinion(
            expert_id="E4",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
        ),
    ]
