"""Czech BeCoMe step display utilities."""
# ruff: noqa: RUF001

from src.calculators.base_calculator import BaseAggregationCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

from .formatting import display_centroid, print_section


def display_step_1_arithmetic_mean(
    opinions: list[ExpertOpinion], calculator: BaseAggregationCalculator
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 1: Arithmetic Mean calculation with detailed output in Czech.

    :param opinions: List of expert opinions
    :param calculator: Calculator instance to use
    :return: Tuple of (mean fuzzy number, mean centroid)
    """
    print_section("KROK 1: Aritmetický průměr (Γ)")

    print("\nVzorec: α = (1/M) × Σ(Ak), γ = (1/M) × Σ(Ck), β = (1/M) × Σ(Bk)")
    print("Kde: α = dolní hranice, γ = vrchol, β = horní hranice")

    mean = calculator.calculate_arithmetic_mean(opinions)
    m = len(opinions)

    sum_lower = mean.lower_bound * m
    sum_peak = mean.peak * m
    sum_upper = mean.upper_bound * m

    print(f"\nSoučet dolních hranic: {sum_lower}")
    print(f"Součet vrcholů: {sum_peak}")
    print(f"Součet horních hranic: {sum_upper}")

    print(
        f"\nAritmetický průměr: Γ({mean.lower_bound:.2f}, {mean.peak:.2f}, {mean.upper_bound:.2f})"
    )
    print(f"  α (dolní hranice) = {sum_lower} / {m} = {mean.lower_bound:.2f}")
    print(f"  γ (vrchol) = {sum_peak} / {m} = {mean.peak:.2f}")
    print(f"  β (horní hranice) = {sum_upper} / {m} = {mean.upper_bound:.2f}")

    mean_centroid = mean.centroid
    display_centroid(mean, "Těžiště průměru")

    return mean, mean_centroid


def display_median_calculation_details(
    sorted_opinions: list[ExpertOpinion], m: int, is_likert: bool = False
) -> None:
    """
    Display median calculation details for odd or even number of experts in Czech.

    :param sorted_opinions: Opinions sorted by centroid
    :param m: Number of experts
    :param is_likert: Whether to display as Likert scale values
    """
    parity = "SUDÝ" if m % 2 == 0 else "LICHÝ"
    print(f"\nPočet expertů je {parity} (M={m})")

    if m % 2 == 0:
        n = m // 2
        left_idx = n - 1
        right_idx = n

        left_op = sorted_opinions[left_idx]
        right_op = sorted_opinions[right_idx]

        print(f"Medián = průměr {left_idx + 1}. a {right_idx + 1}. experta:")
        if is_likert:
            print(f"  {left_idx + 1}.: {left_op.expert_id} → {int(left_op.opinion.peak)}")
            print(f"  {right_idx + 1}.: {right_op.expert_id} → {int(right_op.opinion.peak)}")
        else:
            print(
                f"  {left_idx + 1}.: {left_op.expert_id} → {left_op.opinion} "
                f"(těžiště: {left_op.opinion.centroid:.2f})"
            )
            print(
                f"  {right_idx + 1}.: {right_op.expert_id} → {right_op.opinion} "
                f"(těžiště: {right_op.opinion.centroid:.2f})"
            )
    else:
        middle_idx = m // 2
        middle_op = sorted_opinions[middle_idx]
        print(f"Medián = střední expert (pozice {middle_idx + 1}):")
        if is_likert:
            print(f"  {middle_op.expert_id} → {int(middle_op.opinion.peak)}")
        else:
            print(
                f"  {middle_op.expert_id} → {middle_op.opinion} "
                f"(těžiště: {middle_op.opinion.centroid:.2f})"
            )


def display_step_2_median(
    opinions: list[ExpertOpinion], calculator: BaseAggregationCalculator, is_likert: bool = False
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 2: Median calculation with detailed output in Czech.

    :param opinions: List of expert opinions
    :param calculator: Calculator instance to use
    :param is_likert: Whether this is Likert scale data
    :return: Tuple of (median fuzzy number, median centroid)
    """
    print_section("KROK 2: Medián (Ω)")

    if is_likert:
        print("\nŘazení expertů podle hodnoty (těžiště)...")
    else:
        print("\nŘazení expertů podle těžiště...")

    median = calculator.calculate_median(opinions)
    sorted_opinions = calculator.sort_by_centroid(opinions)
    m = len(sorted_opinions)

    display_median_calculation_details(sorted_opinions, m, is_likert)

    print(f"\nMedián: Ω({median.lower_bound:.2f}, {median.peak:.2f}, {median.upper_bound:.2f})")

    if m % 2 == 0:
        n = m // 2
        left_op = sorted_opinions[n - 1]
        right_op = sorted_opinions[n]

        if is_likert:
            print(
                f"  Všechny složky = ({int(left_op.opinion.peak)} + "
                f"{int(right_op.opinion.peak)}) / 2 = {median.peak:.2f}"
            )
        else:
            print(
                f"  ρ (dolní hranice) = ({left_op.opinion.lower_bound} + "
                f"{right_op.opinion.lower_bound}) / 2 = {median.lower_bound:.2f}"
            )
            print(
                f"  ω (vrchol) = ({left_op.opinion.peak} + "
                f"{right_op.opinion.peak}) / 2 = {median.peak:.2f}"
            )
            print(
                f"  σ (horní hranice) = ({left_op.opinion.upper_bound} + "
                f"{right_op.opinion.upper_bound}) / 2 = {median.upper_bound:.2f}"
            )
    elif m % 2 == 1:
        if not is_likert:
            print(f"  ρ (dolní hranice) = {median.lower_bound:.2f} (od středního experta)")
            print(f"  ω (vrchol) = {median.peak:.2f} (od středního experta)")
            print(f"  σ (horní hranice) = {median.upper_bound:.2f} (od středního experta)")

    median_centroid = median.centroid
    if is_likert:
        print(f"\nTěžiště mediánu: {median_centroid:.2f}")
    else:
        display_centroid(median, "Těžiště mediánu")

    return median, median_centroid


def display_step_3_best_compromise(
    mean: FuzzyTriangleNumber, median: FuzzyTriangleNumber
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 3: Best Compromise calculation in Czech.

    :param mean: Arithmetic mean fuzzy number
    :param median: Median fuzzy number
    :return: Tuple of (best compromise fuzzy number, best compromise centroid)
    """
    print_section("KROK 3: Nejlepší kompromis (ΓΩMean)")

    print("\nVzorec: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2")

    best_compromise = FuzzyTriangleNumber.average([mean, median])

    print(
        f"\nπ (dolní hranice) = ({mean.lower_bound:.2f} + {median.lower_bound:.2f}) / 2 = "
        f"{best_compromise.lower_bound:.2f}"
    )
    print(f"φ (vrchol) = ({mean.peak:.2f} + {median.peak:.2f}) / 2 = {best_compromise.peak:.2f}")
    print(
        f"ξ (horní hranice) = ({mean.upper_bound:.2f} + {median.upper_bound:.2f}) / 2 = "
        f"{best_compromise.upper_bound:.2f}"
    )

    best_compromise_centroid = best_compromise.centroid
    print(
        f"\nNejlepší kompromis: ΓΩMean({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(
        f"Těžiště nejlepšího kompromisu: "
        f"({best_compromise.lower_bound:.2f} + {best_compromise.peak:.2f} + "
        f"{best_compromise.upper_bound:.2f}) / 3 = {best_compromise_centroid:.2f}"
    )

    return best_compromise, best_compromise_centroid


def display_step_4_max_error(mean_centroid: float, median_centroid: float) -> float:
    """
    Display STEP 4: Maximum Error calculation in Czech.

    :param mean_centroid: Centroid of arithmetic mean
    :param median_centroid: Centroid of median
    :return: Maximum error value (precision indicator)
    """
    print_section("KROK 4: Maximální chyba (Δmax)")

    print("\nVzorec: Δmax = |těžiště(Γ) - těžiště(Ω)| / 2")
    print("Ukazatel přesnosti (nižší = lepší)")

    max_error = abs(mean_centroid - median_centroid) / 2

    print(f"\nTěžiště průměru (Gx): {mean_centroid:.2f}")
    print(f"Těžiště mediánu (Gx): {median_centroid:.2f}")
    print(f"Δmax = |{mean_centroid:.2f} - {median_centroid:.2f}| / 2 = {max_error:.2f}")

    return max_error
