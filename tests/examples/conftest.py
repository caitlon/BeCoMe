"""
Shared pytest fixtures for examples tests.

Following Lott's "Python Object-Oriented Programming" (Chapter 13) best practices:
- Fixtures provide test data via Dependency Injection pattern
- Shared fixtures reduce code duplication (DRY principle)
- Proper scoping optimizes test performance
- Type hints ensure type safety and clarity
"""

from pathlib import Path
from typing import Any

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


# ============================================================================
# File Path Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def example_data_dir() -> Path:
    """
    Provide path to example data directory.

    Using scope="session" as the directory path is constant throughout
    the entire test session, optimizing performance by creating it once.

    Returns:
        Path to examples/data directory
    """
    return Path("examples/data")


@pytest.fixture
def budget_case_file(example_data_dir: Path) -> str:
    """
    Provide path to budget case text file.

    Args:
        example_data_dir: Path to examples data directory (injected fixture)

    Returns:
        String path to budget_case.txt file
    """
    return str(example_data_dir / "budget_case.txt")


@pytest.fixture
def floods_case_file(example_data_dir: Path) -> str:
    """
    Provide path to floods case text file.

    Args:
        example_data_dir: Path to examples data directory (injected fixture)

    Returns:
        String path to floods_case.txt file
    """
    return str(example_data_dir / "floods_case.txt")


@pytest.fixture
def pendlers_case_file(example_data_dir: Path) -> str:
    """
    Provide path to pendlers case text file.

    Args:
        example_data_dir: Path to examples data directory (injected fixture)

    Returns:
        String path to pendlers_case.txt file
    """
    return str(example_data_dir / "pendlers_case.txt")


@pytest.fixture
def all_example_files(
    budget_case_file: str, floods_case_file: str, pendlers_case_file: str
) -> dict[str, str]:
    """
    Provide dictionary of all example data file paths.

    Args:
        budget_case_file: Path to budget case file (injected fixture)
        floods_case_file: Path to floods case file (injected fixture)
        pendlers_case_file: Path to pendlers case file (injected fixture)

    Returns:
        Dictionary mapping case names to file paths
    """
    return {
        "budget": budget_case_file,
        "floods": floods_case_file,
        "pendlers": pendlers_case_file,
    }


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
            opinion=FuzzyTriangleNumber(
                lower_bound=10.0 * i, peak=20.0 * i, upper_bound=30.0 * i
            ),
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
        ExpertOpinion(expert_id=f"E{i+1}", opinion=FuzzyTriangleNumber(v, v, v))
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
        ExpertOpinion(expert_id=f"E{i+1}", opinion=FuzzyTriangleNumber(v, v, v))
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
