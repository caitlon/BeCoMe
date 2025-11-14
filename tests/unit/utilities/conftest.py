"""Shared pytest fixtures for utilities tests."""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture(scope="class")
def calculator() -> BeCoMeCalculator:
    """Provide a BeCoMeCalculator instance for tests.

    :return: BeCoMeCalculator instance for performing calculations
    """
    return BeCoMeCalculator()


@pytest.fixture
def sample_three_opinions() -> list[ExpertOpinion]:
    """Provide standard 3-expert opinions for display tests.

    :return: List of 3 ExpertOpinion objects
    """
    return [
        ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
        ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
        ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
    ]


@pytest.fixture
def sample_four_opinions() -> list[ExpertOpinion]:
    """Provide 4-expert opinions for display tests.

    :return: List of 4 ExpertOpinion objects
    """
    return [
        ExpertOpinion(
            expert_id=f"E{i}",
            opinion=FuzzyTriangleNumber(lower_bound=10.0 * i, peak=20.0 * i, upper_bound=30.0 * i),
        )
        for i in range(1, 5)
    ]


@pytest.fixture
def likert_opinions_odd() -> list[ExpertOpinion]:
    """Provide Likert scale opinions with odd number of experts.

    :return: List of 3 ExpertOpinion objects with crisp values
    """
    values = [25.0, 50.0, 75.0]
    return [
        ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
        for i, v in enumerate(values)
    ]


@pytest.fixture
def likert_opinions_even() -> list[ExpertOpinion]:
    """Provide Likert scale opinions with even number of experts.

    :return: List of 4 ExpertOpinion objects with crisp values
    """
    values = [25.0, 50.0, 75.0, 100.0]
    return [
        ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
        for i, v in enumerate(values)
    ]


@pytest.fixture
def single_expert_opinion() -> list[ExpertOpinion]:
    """Provide single expert opinion for edge case testing.

    :return: List containing 1 ExpertOpinion object
    """
    return [ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0))]


@pytest.fixture
def expected_metadata_keys() -> list[str]:
    """Provide list of expected metadata keys from data files.

    :return: List of metadata keys
    """
    return ["case", "description", "num_experts"]


@pytest.fixture
def opinions_factory():
    """Factory fixture to create opinions with varying counts and types.

    :return: Callable that creates list of ExpertOpinion based on parameters
    """

    def _create_opinions(num_experts: int, is_likert: bool = False) -> list[ExpertOpinion]:
        """Create expert opinions with specified count and type.

        :param num_experts: Number of expert opinions to create
        :param is_likert: If True, create Likert scale opinions
        :return: List of ExpertOpinion objects
        """
        if is_likert:
            values = [25.0 * (i + 1) for i in range(num_experts)]
            return [
                ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
                for i, v in enumerate(values)
            ]
        else:
            return [
                ExpertOpinion(
                    expert_id=f"E{i + 1}",
                    opinion=FuzzyTriangleNumber(
                        lower_bound=10.0 * (i + 1), peak=20.0 * (i + 1), upper_bound=30.0 * (i + 1)
                    ),
                )
                for i in range(num_experts)
            ]

    return _create_opinions
