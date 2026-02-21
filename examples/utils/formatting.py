"""Display formatting utilities for BeCoMe examples."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models.fuzzy_number import FuzzyTriangleNumber

if TYPE_CHECKING:
    from src.models.expert_opinion import ExpertOpinion

    from .labels import FormattingLabels


def print_header(title: str, width: int = 60) -> None:
    """
    Print formatted header with title.

    :param title: Title text to display
    :param width: Total width of the header in characters
    """
    width = max(width, len(title))
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_section(title: str, width: int = 60) -> None:
    """
    Print formatted section divider with title.

    :param title: Section title
    :param width: Total width of the divider in characters
    """
    width = max(width, len(title) + 2)
    padding_left: int = (width - len(title) - 2) // 2
    padding_right: int = width - len(title) - 2 - padding_left
    print("\n" + "-" * padding_left + f" {title} " + "-" * padding_right)


def display_case_header(
    case_name: str,
    opinions: list[ExpertOpinion],
    metadata: dict[str, str],
    labels: FormattingLabels | None = None,
) -> None:
    """
    Display case study header with metadata.

    :param case_name: Name of the case study (e.g., "BUDGET CASE")
    :param opinions: List of expert opinions
    :param metadata: Metadata dictionary with case info
    :param labels: Locale-specific labels. Defaults to English.
    """
    if labels is None:
        from .locales import EN_FORMATTING

        labels = EN_FORMATTING

    print_header(f"{case_name} - {labels.detailed_analysis}")
    fallback = labels.not_available_label
    print(f"\n{labels.case_label}: {metadata.get('case', fallback)}")
    print(f"{labels.description_label}: {metadata.get('description', fallback)}")
    parity = labels.even_label if len(opinions) % 2 == 0 else labels.odd_label
    print(f"{labels.num_experts_label}: {len(opinions)} ({parity})")


def display_centroid(
    fuzzy_number: FuzzyTriangleNumber,
    name: str | None = None,
    labels: FormattingLabels | None = None,
) -> None:
    """
    Display centroid calculation in standard format.

    :param fuzzy_number: Fuzzy number to display centroid for
    :param name: Label for the centroid (e.g., "Mean centroid").
                 Falls back to ``labels.default_centroid_name`` if not provided.
    :param labels: Locale-specific labels. Defaults to English.
    """
    if labels is None:
        from .locales import EN_FORMATTING

        labels = EN_FORMATTING
    if name is None:
        name = labels.default_centroid_name

    centroid = fuzzy_number.centroid
    print(
        f"\n{name}: ({fuzzy_number.lower_bound:.2f} + "
        f"{fuzzy_number.peak:.2f} + {fuzzy_number.upper_bound:.2f}) / 3 = "
        f"{centroid:.2f}"
    )
