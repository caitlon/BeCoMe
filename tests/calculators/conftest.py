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


# Fixtures for compromise tests


@pytest.fixture
def four_experts_even_opinions():
    """Provide opinions from 4 experts (even number)."""
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


@pytest.fixture
def five_experts_skewed_opinions():
    """
    Provide 5 experts with skewed distribution.

    Creates scenario where mean and median differ significantly.
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=3.0, upper_bound=4.0),
        ),
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=4.0, upper_bound=5.0),
        ),
        ExpertOpinion(
            expert_id="E4",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
        ),
        ExpertOpinion(
            expert_id="E5",
            opinion=FuzzyTriangleNumber(lower_bound=11.0, peak=12.0, upper_bound=13.0),
        ),
    ]


@pytest.fixture
def two_experts_for_error_calculation():
    """Provide two experts for testing error calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=0.0, peak=5.0, upper_bound=10.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
        ),
    ]


# Fixtures for median tests


@pytest.fixture
def two_experts_for_median():
    """Provide opinions from 2 experts for median calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
        ),
    ]


@pytest.fixture
def five_experts_for_median():
    """Provide opinions from 5 experts for median calculation."""
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
        ExpertOpinion(
            expert_id="E5",
            opinion=FuzzyTriangleNumber(lower_bound=13.0, peak=14.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def six_experts_for_median():
    """Provide opinions from 6 experts for median calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=3.0, upper_bound=4.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
        ),
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=7.0, upper_bound=8.0),
        ),
        ExpertOpinion(
            expert_id="E4",
            opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=9.0, upper_bound=10.0),
        ),
        ExpertOpinion(
            expert_id="E5",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=11.0, upper_bound=12.0),
        ),
        ExpertOpinion(
            expert_id="E6",
            opinion=FuzzyTriangleNumber(lower_bound=12.0, peak=13.0, upper_bound=14.0),
        ),
    ]


@pytest.fixture
def seven_experts_for_median():
    """Provide opinions from 7 experts for median calculation."""
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=2.0, peak=3.0, upper_bound=4.0),
        ),
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=4.0, upper_bound=5.0),
        ),
        ExpertOpinion(
            expert_id="E4",
            opinion=FuzzyTriangleNumber(lower_bound=4.0, peak=5.0, upper_bound=6.0),
        ),
        ExpertOpinion(
            expert_id="E5",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=6.0, upper_bound=7.0),
        ),
        ExpertOpinion(
            expert_id="E6",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=7.0, upper_bound=8.0),
        ),
        ExpertOpinion(
            expert_id="E7",
            opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=8.0, upper_bound=9.0),
        ),
    ]


@pytest.fixture
def three_experts_unsorted():
    """Provide unsorted opinions to test sorting by centroid."""
    return [
        ExpertOpinion(
            expert_id="High",
            opinion=FuzzyTriangleNumber(lower_bound=15.0, peak=18.0, upper_bound=21.0),
        ),  # centroid = 18.0
        ExpertOpinion(
            expert_id="Low",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        ),  # centroid = 6.0
        ExpertOpinion(
            expert_id="Mid",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        ),  # centroid = 12.0
    ]
