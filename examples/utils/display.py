"""BeCoMe step display utilities."""
# ruff: noqa: RUF001

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models.fuzzy_number import FuzzyTriangleNumber

from .formatting import display_centroid, print_section

if TYPE_CHECKING:
    from src.calculators.base_calculator import BaseAggregationCalculator
    from src.models.expert_opinion import ExpertOpinion

    from .labels import DisplayLabels


def _default_display_labels() -> DisplayLabels:
    from .locales import EN_DISPLAY

    return EN_DISPLAY


def display_step_1_arithmetic_mean(
    opinions: list[ExpertOpinion],
    calculator: BaseAggregationCalculator,
    labels: DisplayLabels | None = None,
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 1: Arithmetic Mean calculation with detailed output.

    :param opinions: List of expert opinions
    :param calculator: Calculator instance to use
    :param labels: Locale-specific labels. Defaults to English.
    :return: Tuple of (mean fuzzy number, mean centroid)
    """
    if labels is None:
        labels = _default_display_labels()

    print_section(labels.step_1_title)

    print(f"\n{labels.formula_step_1}")
    print(labels.formula_where)

    mean = calculator.calculate_arithmetic_mean(opinions)
    m = len(opinions)

    sum_lower = mean.lower_bound * m
    sum_peak = mean.peak * m
    sum_upper = mean.upper_bound * m

    print(f"\n{labels.sum_lower_label}: {sum_lower}")
    print(f"{labels.sum_peaks_label}: {sum_peak}")
    print(f"{labels.sum_upper_label}: {sum_upper}")

    print(
        f"\n{labels.arithmetic_mean_label}: "
        f"Γ({mean.lower_bound:.2f}, {mean.peak:.2f}, {mean.upper_bound:.2f})"
    )
    print(f"  α ({labels.lower_pos}) = {sum_lower} / {m} = {mean.lower_bound:.2f}")
    print(f"  γ ({labels.peak_pos}) = {sum_peak} / {m} = {mean.peak:.2f}")
    print(f"  β ({labels.upper_pos}) = {sum_upper} / {m} = {mean.upper_bound:.2f}")

    mean_centroid = mean.centroid
    display_centroid(mean, labels.mean_centroid_name)

    return mean, mean_centroid


def display_median_calculation_details(
    sorted_opinions: list[ExpertOpinion],
    m: int,
    is_likert: bool = False,
    labels: DisplayLabels | None = None,
) -> None:
    """
    Display median calculation details for odd or even number of experts.

    :param sorted_opinions: Opinions sorted by centroid
    :param m: Number of experts
    :param is_likert: Whether to display as Likert scale values
    :param labels: Locale-specific labels. Defaults to English.
    """
    if labels is None:
        labels = _default_display_labels()

    parity = labels.even_upper if m % 2 == 0 else labels.odd_upper
    print(f"\n{labels.expert_count_template.format(parity=parity, m=m)}")

    if m % 2 == 0:
        n = m // 2
        left_idx = n - 1
        right_idx = n

        left_op = sorted_opinions[left_idx]
        right_op = sorted_opinions[right_idx]

        print(labels.median_even_template.format(left=left_idx + 1, right=right_idx + 1))
        if is_likert:
            print(f"  {left_idx + 1}: {left_op.expert_id} -> {int(left_op.opinion.peak)}")
            print(f"  {right_idx + 1}: {right_op.expert_id} -> {int(right_op.opinion.peak)}")
        else:
            print(
                f"  {left_idx + 1}: {left_op.expert_id} -> {left_op.opinion} "
                f"({labels.centroid_word}: {left_op.opinion.centroid:.2f})"
            )
            print(
                f"  {right_idx + 1}: {right_op.expert_id} -> {right_op.opinion} "
                f"({labels.centroid_word}: {right_op.opinion.centroid:.2f})"
            )
    else:
        middle_idx = m // 2
        middle_op = sorted_opinions[middle_idx]
        print(labels.median_odd_template.format(pos=middle_idx + 1))
        if is_likert:
            print(f"  {middle_op.expert_id} -> {int(middle_op.opinion.peak)}")
        else:
            print(
                f"  {middle_op.expert_id} -> {middle_op.opinion} "
                f"({labels.centroid_word}: {middle_op.opinion.centroid:.2f})"
            )


def display_step_2_median(
    opinions: list[ExpertOpinion],
    calculator: BaseAggregationCalculator,
    is_likert: bool = False,
    labels: DisplayLabels | None = None,
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 2: Median calculation with detailed output.

    :param opinions: List of expert opinions
    :param calculator: Calculator instance to use
    :param is_likert: Whether this is Likert scale data
    :param labels: Locale-specific labels. Defaults to English.
    :return: Tuple of (median fuzzy number, median centroid)
    """
    if labels is None:
        labels = _default_display_labels()

    print_section(labels.step_2_title)

    if is_likert:
        print(f"\n{labels.sorting_by_value}")
    else:
        print(f"\n{labels.sorting_by_centroid}")

    median = calculator.calculate_median(opinions)
    sorted_opinions = calculator.sort_by_centroid(opinions)
    m = len(sorted_opinions)

    display_median_calculation_details(sorted_opinions, m, is_likert, labels)

    print(
        f"\n{labels.median_result_label}: "
        f"Ω({median.lower_bound:.2f}, {median.peak:.2f}, {median.upper_bound:.2f})"
    )

    if m % 2 == 0:
        n = m // 2
        left_op = sorted_opinions[n - 1]
        right_op = sorted_opinions[n]

        if is_likert:
            print(
                f"  {labels.all_components_label} = ({int(left_op.opinion.peak)} + "
                f"{int(right_op.opinion.peak)}) / 2 = {median.peak:.2f}"
            )
        else:
            print(
                f"  ρ ({labels.lower_pos}) = ({left_op.opinion.lower_bound} + "
                f"{right_op.opinion.lower_bound}) / 2 = {median.lower_bound:.2f}"
            )
            print(
                f"  ω ({labels.peak_pos}) = ({left_op.opinion.peak} + "
                f"{right_op.opinion.peak}) / 2 = {median.peak:.2f}"
            )
            print(
                f"  σ ({labels.upper_pos}) = ({left_op.opinion.upper_bound} + "
                f"{right_op.opinion.upper_bound}) / 2 = {median.upper_bound:.2f}"
            )
    else:
        if not is_likert:
            print(
                f"  ρ ({labels.lower_pos}) = {median.lower_bound:.2f} ({labels.from_middle_expert})"
            )
            print(f"  ω ({labels.peak_pos}) = {median.peak:.2f} ({labels.from_middle_expert})")
            print(
                f"  σ ({labels.upper_pos}) = {median.upper_bound:.2f} ({labels.from_middle_expert})"
            )

    median_centroid = median.centroid
    if is_likert:
        print(f"\n{labels.median_centroid_name}: {median_centroid:.2f}")
    else:
        display_centroid(median, labels.median_centroid_name)

    return median, median_centroid


def display_step_3_best_compromise(
    mean: FuzzyTriangleNumber,
    median: FuzzyTriangleNumber,
    labels: DisplayLabels | None = None,
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 3: Best Compromise calculation.

    :param mean: Arithmetic mean fuzzy number
    :param median: Median fuzzy number
    :param labels: Locale-specific labels. Defaults to English.
    :return: Tuple of (best compromise fuzzy number, best compromise centroid)
    """
    if labels is None:
        labels = _default_display_labels()

    print_section(labels.step_3_title)

    print(f"\n{labels.formula_step_3}")

    best_compromise = FuzzyTriangleNumber.average([mean, median])

    print(
        f"\nπ ({labels.lower_pos}) = ({mean.lower_bound:.2f} + {median.lower_bound:.2f}) / 2 = "
        f"{best_compromise.lower_bound:.2f}"
    )
    print(
        f"φ ({labels.peak_pos}) = ({mean.peak:.2f} + {median.peak:.2f}) / 2 = "
        f"{best_compromise.peak:.2f}"
    )
    print(
        f"ξ ({labels.upper_pos}) = ({mean.upper_bound:.2f} + {median.upper_bound:.2f}) / 2 = "
        f"{best_compromise.upper_bound:.2f}"
    )

    best_compromise_centroid = best_compromise.centroid
    print(
        f"\n{labels.best_compromise_label}: ΓΩMean({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(
        f"{labels.bc_centroid_label}: "
        f"({best_compromise.lower_bound:.2f} + {best_compromise.peak:.2f} + "
        f"{best_compromise.upper_bound:.2f}) / 3 = {best_compromise_centroid:.2f}"
    )

    return best_compromise, best_compromise_centroid


def display_step_4_max_error(
    mean_centroid: float,
    median_centroid: float,
    labels: DisplayLabels | None = None,
) -> float:
    """
    Display STEP 4: Maximum Error calculation.

    :param mean_centroid: Centroid of arithmetic mean
    :param median_centroid: Centroid of median
    :param labels: Locale-specific labels. Defaults to English.
    :return: Maximum error value (precision indicator)
    """
    if labels is None:
        labels = _default_display_labels()

    print_section(labels.step_4_title)

    print(f"\n{labels.formula_step_4}")
    print(labels.precision_note)

    max_error = abs(mean_centroid - median_centroid) / 2

    print(f"\n{labels.mean_centroid_gx}: {mean_centroid:.2f}")
    print(f"{labels.median_centroid_gx}: {median_centroid:.2f}")
    print(f"Δmax = |{mean_centroid:.2f} - {median_centroid:.2f}| / 2 = {max_error:.2f}")

    return max_error
