"""
Shared pytest fixtures for utilities tests.

Following Lott's "Python Object-Oriented Programming" (Chapter 13) best practices:
- Fixtures provide test data via Dependency Injection pattern
- Shared fixtures reduce code duplication (DRY principle)
- Proper scoping optimizes test performance
- Type hints ensure type safety and clarity
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# ============================================================================
# Calculator Fixtures
# ============================================================================


@pytest.fixture(scope="class")
def calculator() -> BeCoMeCalculator:
    """
    Provide a BeCoMeCalculator instance for tests.

    Using scope="class" as recommended by Lott: creates the calculator
    once per test class, reducing object creation overhead while maintaining
    test isolation (calculator is stateless).

    Returns:
        BeCoMeCalculator instance for performing calculations
    """
    return BeCoMeCalculator()


# ============================================================================
# Test Data Fixtures - Expert Opinions
# ============================================================================


@pytest.fixture
def sample_three_opinions() -> list[ExpertOpinion]:
    """
    Provide standard 3-expert opinions for display tests.

    Returns three expert opinions with sequential triangular fuzzy numbers,
    useful for testing odd-number expert scenarios.

    Returns:
        List of 3 ExpertOpinion objects with values:
        - E1: (10.0, 20.0, 30.0)
        - E2: (15.0, 25.0, 35.0)
        - E3: (20.0, 30.0, 40.0)
    """
    return [
        ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0)),
        ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(15.0, 25.0, 35.0)),
        ExpertOpinion(expert_id="E3", opinion=FuzzyTriangleNumber(20.0, 30.0, 40.0)),
    ]


@pytest.fixture
def sample_four_opinions() -> list[ExpertOpinion]:
    """
    Provide 4-expert opinions (even number) for display tests.

    Returns four expert opinions with scaled triangular fuzzy numbers,
    useful for testing even-number expert scenarios.

    Returns:
        List of 4 ExpertOpinion objects with scaled values
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
    """
    Provide Likert scale opinions with odd number of experts (crisp values).

    Likert scale opinions have equal lower, peak, and upper bounds,
    representing crisp values from a discrete scale.

    Returns:
        List of 3 ExpertOpinion objects with Likert scale values:
        - E1: 25.0 (all bounds equal)
        - E2: 50.0 (all bounds equal)
        - E3: 75.0 (all bounds equal)
    """
    values = [25.0, 50.0, 75.0]
    return [
        ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
        for i, v in enumerate(values)
    ]


@pytest.fixture
def likert_opinions_even() -> list[ExpertOpinion]:
    """
    Provide Likert scale opinions with even number of experts (crisp values).

    Likert scale opinions have equal lower, peak, and upper bounds,
    representing crisp values from a discrete scale.

    Returns:
        List of 4 ExpertOpinion objects with Likert scale values:
        - E1: 25.0 (all bounds equal)
        - E2: 50.0 (all bounds equal)
        - E3: 75.0 (all bounds equal)
        - E4: 100.0 (all bounds equal)
    """
    values = [25.0, 50.0, 75.0, 100.0]
    return [
        ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
        for i, v in enumerate(values)
    ]


@pytest.fixture
def single_expert_opinion() -> list[ExpertOpinion]:
    """
    Provide single expert opinion for edge case testing.

    Returns:
        List containing 1 ExpertOpinion object with value (10.0, 20.0, 30.0)
    """
    return [ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(10.0, 20.0, 30.0))]


# ============================================================================
# Test Metadata Fixtures
# ============================================================================


@pytest.fixture
def expected_metadata_keys() -> list[str]:
    """
    Provide list of expected metadata keys from data files.

    Returns:
        List of metadata keys that should be present after loading
    """
    return ["case", "description", "num_experts"]


# ============================================================================
# Factory Fixtures for Parametrized Tests
# ============================================================================


@pytest.fixture
def opinions_factory():
    """
    Factory fixture to create opinions with varying counts and types.

    This factory allows parametrized tests to generate test data dynamically
    while maintaining the DRY principle.

    Returns:
        Callable that creates list of ExpertOpinion based on parameters
    """

    def _create_opinions(num_experts: int, is_likert: bool = False) -> list[ExpertOpinion]:
        """
        Create expert opinions with specified count and type.

        Args:
            num_experts: Number of expert opinions to create
            is_likert: If True, create Likert scale (crisp) opinions

        Returns:
            List of ExpertOpinion objects
        """
        if is_likert:
            # Likert scale: crisp values (lower = peak = upper)
            values = [25.0 * (i + 1) for i in range(num_experts)]
            return [
                ExpertOpinion(expert_id=f"E{i + 1}", opinion=FuzzyTriangleNumber(v, v, v))
                for i, v in enumerate(values)
            ]
        else:
            # Fuzzy triangular numbers with scaled values
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
