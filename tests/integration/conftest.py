"""
Shared pytest fixtures for integration tests.

Following Lott's "Python Object-Oriented Programming" (Chapter 13) best practices:
- Fixtures provide test data via Dependency Injection pattern
- Shared fixtures reduce code duplication (DRY principle)
- Proper scoping optimizes test performance
- Type hints ensure type safety and clarity
"""

from pathlib import Path

import pytest

from src.calculators.become_calculator import BeCoMeCalculator

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
