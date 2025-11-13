"""Display formatting utilities for BeCoMe examples."""

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


def print_header(title: str, width: int = 60) -> None:
    """
    Print formatted header with title.

    :param title: Title text to display
    :param width: Total width of the header in characters
    """
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_section(title: str, width: int = 60) -> None:
    """
    Print formatted section divider with title.

    :param title: Section title
    :param width: Total width of the divider in characters
    """
    padding: int = (width - len(title) - 2) // 2
    print("\n" + "-" * padding + f" {title} " + "-" * padding)


def display_case_header(
    case_name: str,
    opinions: list[ExpertOpinion],
    metadata: dict[str, str],
) -> None:
    """
    Display case study header with metadata.

    :param case_name: Name of the case study (e.g., "BUDGET CASE")
    :param opinions: List of expert opinions
    :param metadata: Metadata dictionary with case info
    """
    print_header(f"{case_name} - DETAILED ANALYSIS")
    print(f"\nCase: {metadata['case']}")
    print(f"Description: {metadata['description']}")
    print(f"Number of experts: {len(opinions)} ({'even' if len(opinions) % 2 == 0 else 'odd'})")


def display_centroid(fuzzy_number: FuzzyTriangleNumber, name: str = "Centroid") -> None:
    """
    Display centroid calculation in standard format.

    :param fuzzy_number: Fuzzy number to display centroid for
    :param name: Label for the centroid (e.g., "Mean centroid")
    """

    centroid = fuzzy_number.centroid
    print(
        f"\n{name}: ({fuzzy_number.lower_bound:.2f} + "
        f"{fuzzy_number.peak:.2f} + {fuzzy_number.upper_bound:.2f}) / 3 = "
        f"{centroid:.2f}"
    )
