"""Shared pytest fixtures for integration tests."""

from pathlib import Path

import pytest

from src.calculators.become_calculator import BeCoMeCalculator


@pytest.fixture(scope="class")
def calculator() -> BeCoMeCalculator:
    """
    BeCoMeCalculator instance for tests.

    :return: BeCoMeCalculator instance
    """
    return BeCoMeCalculator()


@pytest.fixture(scope="session")
def example_data_dir() -> Path:
    """
    Path to example data directory.

    :return: Path to examples/data directory
    """
    return Path("examples/data")


@pytest.fixture
def budget_case_file(example_data_dir: Path) -> str:
    """
    Path to budget case text file.

    :param example_data_dir: Path to examples data directory
    :return: String path to budget_case.txt file
    """
    return str(example_data_dir / "budget_case.txt")


@pytest.fixture
def floods_case_file(example_data_dir: Path) -> str:
    """
    Path to floods case text file.

    :param example_data_dir: Path to examples data directory
    :return: String path to floods_case.txt file
    """
    return str(example_data_dir / "floods_case.txt")


@pytest.fixture
def pendlers_case_file(example_data_dir: Path) -> str:
    """
    Path to pendlers case text file.

    :param example_data_dir: Path to examples data directory
    :return: String path to pendlers_case.txt file
    """
    return str(example_data_dir / "pendlers_case.txt")
