"""English BeCoMe step display utilities."""
# ruff: noqa: RUF001

from src.calculators.base_calculator import BaseAggregationCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

from .formatting import display_centroid, print_section


def display_step_1_arithmetic_mean(
    opinions: list[ExpertOpinion], calculator: BaseAggregationCalculator
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 1: Arithmetic Mean calculation with detailed output.

    :param opinions: List of expert opinions
    :param calculator: Calculator instance to use
    :return: Tuple of (mean fuzzy number, mean centroid)
    """
    print_section("STEP 1: Arithmetic Mean (Gamma)")

    print("\nFormula: α = (1/M) x Σ(Ak), γ = (1/M) x Σ(Ck), β = (1/M) x Σ(Bk)")
    print("Where: α = lower bound, γ = peak, β = upper bound")

    mean = calculator.calculate_arithmetic_mean(opinions)
    m = len(opinions)

    sum_lower = mean.lower_bound * m
    sum_peak = mean.peak * m
    sum_upper = mean.upper_bound * m

    print(f"\nSum of lower bounds: {sum_lower}")
    print(f"Sum of peaks: {sum_peak}")
    print(f"Sum of upper bounds: {sum_upper}")

    print(f"\nArithmetic Mean: Γ({mean.lower_bound:.2f}, {mean.peak:.2f}, {mean.upper_bound:.2f})")
    print(f"  α (lower) = {sum_lower} / {m} = {mean.lower_bound:.2f}")
    print(f"  γ (peak) = {sum_peak} / {m} = {mean.peak:.2f}")
    print(f"  β (upper) = {sum_upper} / {m} = {mean.upper_bound:.2f}")

    mean_centroid = mean.centroid
    display_centroid(mean, "Mean centroid")

    return mean, mean_centroid


def display_median_calculation_details(
    sorted_opinions: list[ExpertOpinion], m: int, is_likert: bool = False
) -> None:
    """
    Display median calculation details for odd or even number of experts.

    :param sorted_opinions: Opinions sorted by centroid
    :param m: Number of experts
    :param is_likert: Whether to display as Likert scale values
    """
    print(f"\nNumber of experts is {'EVEN' if m % 2 == 0 else 'ODD'} (M={m})")

    if m % 2 == 0:
        n = m // 2
        left_idx = n - 1
        right_idx = n

        left_op = sorted_opinions[left_idx]
        right_op = sorted_opinions[right_idx]

        print(f"Median = average of {left_idx + 1}th and {right_idx + 1}th experts:")
        if is_likert:
            print(f"  {left_idx + 1}th: {left_op.expert_id} -> {int(left_op.opinion.peak)}")
            print(f"  {right_idx + 1}th: {right_op.expert_id} -> {int(right_op.opinion.peak)}")
        else:
            print(
                f"  {left_idx + 1}th: {left_op.expert_id} -> {left_op.opinion} "
                f"(centroid: {left_op.opinion.centroid:.2f})"
            )
            print(
                f"  {right_idx + 1}th: {right_op.expert_id} -> {right_op.opinion} "
                f"(centroid: {right_op.opinion.centroid:.2f})"
            )
    else:
        middle_idx = m // 2
        middle_op = sorted_opinions[middle_idx]
        print(f"Median = middle expert (position {middle_idx + 1}):")
        if is_likert:
            print(f"  {middle_op.expert_id} -> {int(middle_op.opinion.peak)}")
        else:
            print(
                f"  {middle_op.expert_id} -> {middle_op.opinion} "
                f"(centroid: {middle_op.opinion.centroid:.2f})"
            )


def display_step_2_median(
    opinions: list[ExpertOpinion], calculator: BaseAggregationCalculator, is_likert: bool = False
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 2: Median calculation with detailed output.

    :param opinions: List of expert opinions
    :param calculator: Calculator instance to use
    :param is_likert: Whether this is Likert scale data
    :return: Tuple of (median fuzzy number, median centroid)
    """
    print_section("STEP 2: Median (Omega)")

    if is_likert:
        print("\nSorting experts by value (centroid)...")
    else:
        print("\nSorting experts by centroid...")

    median = calculator.calculate_median(opinions)
    sorted_opinions = calculator.sort_by_centroid(opinions)
    m = len(sorted_opinions)

    display_median_calculation_details(sorted_opinions, m, is_likert)

    print(f"\nMedian: Ω({median.lower_bound:.2f}, {median.peak:.2f}, {median.upper_bound:.2f})")

    if m % 2 == 0:
        n = m // 2
        left_op = sorted_opinions[n - 1]
        right_op = sorted_opinions[n]

        if is_likert:
            print(
                f"  All components = ({int(left_op.opinion.peak)} + "
                f"{int(right_op.opinion.peak)}) / 2 = {median.peak:.2f}"
            )
        else:
            print(
                f"  ρ (lower) = ({left_op.opinion.lower_bound} + "
                f"{right_op.opinion.lower_bound}) / 2 = {median.lower_bound:.2f}"
            )
            print(
                f"  ω (peak) = ({left_op.opinion.peak} + "
                f"{right_op.opinion.peak}) / 2 = {median.peak:.2f}"
            )
            print(
                f"  σ (upper) = ({left_op.opinion.upper_bound} + "
                f"{right_op.opinion.upper_bound}) / 2 = {median.upper_bound:.2f}"
            )
    elif m % 2 == 1:
        if not is_likert:
            print(f"  ρ (lower) = {median.lower_bound:.2f} (from middle expert)")
            print(f"  ω (peak) = {median.peak:.2f} (from middle expert)")
            print(f"  σ (upper) = {median.upper_bound:.2f} (from middle expert)")

    median_centroid = median.centroid
    if is_likert:
        print(f"\nMedian centroid: {median_centroid:.2f}")
    else:
        display_centroid(median, "Median centroid")

    return median, median_centroid


def display_step_3_best_compromise(
    mean: FuzzyTriangleNumber, median: FuzzyTriangleNumber
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 3: Best Compromise calculation.

    :param mean: Arithmetic mean fuzzy number
    :param median: Median fuzzy number
    :return: Tuple of (best compromise fuzzy number, best compromise centroid)
    """
    print_section("STEP 3: Best Compromise (ΓΩMean)")

    print("\nFormula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2")

    best_compromise = FuzzyTriangleNumber.average([mean, median])

    print(
        f"\nπ (lower) = ({mean.lower_bound:.2f} + {median.lower_bound:.2f}) / 2 = "
        f"{best_compromise.lower_bound:.2f}"
    )
    print(f"φ (peak) = ({mean.peak:.2f} + {median.peak:.2f}) / 2 = {best_compromise.peak:.2f}")
    print(
        f"ξ (upper) = ({mean.upper_bound:.2f} + {median.upper_bound:.2f}) / 2 = "
        f"{best_compromise.upper_bound:.2f}"
    )

    best_compromise_centroid = best_compromise.centroid
    print(
        f"\nBest Compromise: ΓΩMean({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(
        f"Best compromise centroid: "
        f"({best_compromise.lower_bound:.2f} + {best_compromise.peak:.2f} + "
        f"{best_compromise.upper_bound:.2f}) / 3 = {best_compromise_centroid:.2f}"
    )

    return best_compromise, best_compromise_centroid


def display_step_4_max_error(mean_centroid: float, median_centroid: float) -> float:
    """
    Display STEP 4: Maximum Error calculation.

    :param mean_centroid: Centroid of arithmetic mean
    :param median_centroid: Centroid of median
    :return: Maximum error value (precision indicator)
    """
    print_section("STEP 4: Maximum Error (Δmax)")

    print("\nFormula: Δmax = |centroid(Γ) - centroid(Ω)| / 2")
    print("This is the precision indicator (lower is better)")

    max_error = abs(mean_centroid - median_centroid) / 2

    print(f"\nMean centroid (Gx): {mean_centroid:.2f}")
    print(f"Median centroid (Gx): {median_centroid:.2f}")
    print(f"Δmax = |{mean_centroid:.2f} - {median_centroid:.2f}| / 2 = {max_error:.2f}")

    return max_error
