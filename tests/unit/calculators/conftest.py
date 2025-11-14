"""Shared pytest fixtures for calculator unit tests.

This module contains fixtures used across multiple test modules in the
calculators test suite. Each fixture provides test data or configured
objects for the GIVEN phase of test cases.
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture(scope="class")
def calculator():
    """Provide BeCoMeCalculator instance for test classes.

    :return: Configured BeCoMeCalculator instance
    """
    return BeCoMeCalculator()


@pytest.fixture
def three_experts_opinions():
    """Provide opinions from three experts with sequential fuzzy values.

    :return: List of 3 ExpertOpinion instances with sequential triangular fuzzy numbers
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
    """Provide opinion from a single expert.

    :return: List containing one ExpertOpinion instance
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def four_experts_even_opinions():
    """Provide opinions from four experts for even-count median tests.

    :return: List of 4 ExpertOpinion instances with sequential triangular fuzzy numbers
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
