"""Locale-specific labels for BeCoMe example output."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayLabels:
    """Labels used by display step functions.

    Fields with ``_template`` suffix use Python ``str.format()`` placeholders.
    """

    # Shared component position labels
    lower_pos: str
    peak_pos: str
    upper_pos: str

    # Step 1: Arithmetic Mean
    step_1_title: str
    formula_step_1: str
    formula_where: str
    sum_lower_label: str
    sum_peaks_label: str
    sum_upper_label: str
    arithmetic_mean_label: str
    mean_centroid_name: str

    # Step 2: Median — detail sub-function
    expert_count_template: str
    even_upper: str
    odd_upper: str
    median_even_template: str
    median_odd_template: str
    centroid_word: str

    # Step 2: Median — main function
    step_2_title: str
    sorting_by_value: str
    sorting_by_centroid: str
    median_result_label: str
    all_components_label: str
    from_middle_expert: str
    median_centroid_name: str

    # Step 3: Best Compromise
    step_3_title: str
    formula_step_3: str
    best_compromise_label: str
    bc_centroid_label: str

    # Step 4: Maximum Error
    step_4_title: str
    formula_step_4: str
    precision_note: str
    mean_centroid_gx: str
    median_centroid_gx: str


@dataclass(frozen=True)
class FormattingLabels:
    """Labels used by formatting functions."""

    detailed_analysis: str
    case_label: str
    description_label: str
    num_experts_label: str
    even_label: str
    odd_label: str
    default_centroid_name: str


@dataclass(frozen=True)
class AnalysisLabels:
    """Labels for expert agreement level results."""

    good: str
    moderate: str
    low: str
