"""
Utility functions for examples.

This module provides helper functions for loading and processing
data for BeCoMe examples.
"""

from pathlib import Path

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


def load_data_from_txt(filepath: str) -> tuple[list[ExpertOpinion], dict[str, str]]:
    """
    Load expert opinions from a text file.

    The text file should have the following format:
        CASE: CaseName
        DESCRIPTION: Case description
        EXPERTS: N

        # Format: ExpertID | Lower | Peak | Upper
        Expert1 | 10 | 15 | 20
        Expert2 | 12 | 18 | 25
        ...

    Args:
        filepath: Path to the text file

    Returns:
        Tuple of (list of ExpertOpinion objects, metadata dict)
        Metadata dict contains: 'case', 'description', 'num_experts'

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is invalid
    """
    file_path = Path(filepath)

    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    metadata: dict[str, str] = {}
    opinions: list[ExpertOpinion] = []

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comment lines
            if not line or line.startswith("#"):
                continue

            # Parse metadata
            if line.startswith("CASE:"):
                metadata["case"] = line.split("CASE:")[1].strip()
            elif line.startswith("DESCRIPTION:"):
                metadata["description"] = line.split("DESCRIPTION:")[1].strip()
            elif line.startswith("EXPERTS:"):
                metadata["num_experts"] = line.split("EXPERTS:")[1].strip()
            elif "|" in line:
                # Parse expert opinion line
                parts: list[str] = [part.strip() for part in line.split("|")]

                if len(parts) != 4:
                    raise ValueError(
                        f"Invalid line format (expected 4 parts): {line}\n"
                        f"Expected format: ExpertID | Lower | Peak | Upper"
                    )

                expert_id: str = parts[0]
                try:
                    lower: float = float(parts[1])
                    peak: float = float(parts[2])
                    upper: float = float(parts[3])
                except ValueError as e:
                    raise ValueError(f"Invalid numeric values in line: {line}") from e

                # Create fuzzy number and expert opinion
                fuzzy_number = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)
                opinion = ExpertOpinion(expert_id=expert_id, opinion=fuzzy_number)
                opinions.append(opinion)

    # Validate that we loaded the expected number of experts
    if "num_experts" in metadata:
        expected_count: int = int(metadata["num_experts"])
        actual_count: int = len(opinions)
        if actual_count != expected_count:
            raise ValueError(f"Expected {expected_count} experts but loaded {actual_count}")

    return opinions, metadata


def print_header(title: str, width: int = 60) -> None:
    """
    Print a formatted header.

    Args:
        title: Title text to display
        width: Total width of the header
    """
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_section(title: str, width: int = 60) -> None:
    """
    Print a formatted section divider.

    Args:
        title: Section title
        width: Total width of the divider
    """
    padding: int = (width - len(title) - 2) // 2
    print("\n" + "-" * padding + f" {title} " + "-" * padding)
