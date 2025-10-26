"""
Detailed analysis of BUDGET CASE.

This script demonstrates step-by-step BeCoMe calculation for the Budget case study
with 22 experts (even number) providing interval estimates for COVID-19 pandemic
budget support.
"""

# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001

from pathlib import Path

from examples.utils import load_data_from_txt, print_header, print_section
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


def main() -> None:
    """Run detailed analysis of Budget case."""
    # Load data from text file
    data_file: str = str(Path(__file__).parent / "data" / "budget_case.txt")
    opinions: list[ExpertOpinion]
    metadata: dict[str, str]
    opinions, metadata = load_data_from_txt(data_file)

    # Display case information
    print_header("BUDGET CASE - DETAILED ANALYSIS")

    print(f"\nCase: {metadata['case']}")
    print(f"Description: {metadata['description']}")
    print(f"Number of experts: {len(opinions)} ({'even' if len(opinions) % 2 == 0 else 'odd'})")

    # Create calculator
    calculator = BeCoMeCalculator()

    # STEP 1: Calculate Arithmetic Mean (Gamma)
    print_section("STEP 1: Arithmetic Mean (Gamma)")

    print("\nFormula: α = (1/M) × Σ(Ak), γ = (1/M) × Σ(Ck), β = (1/M) × Σ(Bk)")
    print("Where: α = lower bound, γ = peak, β = upper bound")

    # Use calculator method instead of manual calculation
    mean = calculator.calculate_arithmetic_mean(opinions)
    m: int = len(opinions)

    # Calculate sums for display purposes (derived from mean)
    sum_lower: float = mean.lower_bound * m
    sum_peak: float = mean.peak * m
    sum_upper: float = mean.upper_bound * m

    print(f"\nSum of lower bounds: {sum_lower}")
    print(f"Sum of peaks: {sum_peak}")
    print(f"Sum of upper bounds: {sum_upper}")

    print(f"\nArithmetic Mean: Γ({mean.lower_bound:.2f}, {mean.peak:.2f}, {mean.upper_bound:.2f})")
    print(f"  α (lower) = {sum_lower} / {m} = {mean.lower_bound:.2f}")
    print(f"  γ (peak) = {sum_peak} / {m} = {mean.peak:.2f}")
    print(f"  β (upper) = {sum_upper} / {m} = {mean.upper_bound:.2f}")

    # Use the built-in centroid method
    mean_centroid: float = mean.get_centroid()
    print(
        f"\nMean centroid: ({mean.lower_bound:.2f} + {mean.peak:.2f} + {mean.upper_bound:.2f}) / 3 = {mean_centroid:.2f}"
    )

    # STEP 2: Calculate Median (Omega)
    print_section("STEP 2: Median (Omega)")

    print("\nSorting experts by centroid...")
    sorted_opinions: list[ExpertOpinion] = calculator.sort_by_centroid(opinions)

    # Show median calculation
    print(f"\nNumber of experts is {'EVEN' if m % 2 == 0 else 'ODD'} (M={m})")

    if m % 2 == 0:
        # Even case
        n: int = m // 2
        left_idx: int = n - 1
        right_idx: int = n

        left_op = sorted_opinions[left_idx]
        right_op = sorted_opinions[right_idx]

        print(f"Median = average of {left_idx + 1}th and {right_idx + 1}th experts:")
        print(
            f"  {left_idx + 1}th: {left_op.expert_id} → {left_op.opinion} (centroid: {left_op.opinion.get_centroid():.2f})"
        )
        print(
            f"  {right_idx + 1}th: {right_op.expert_id} → {right_op.opinion} (centroid: {right_op.opinion.get_centroid():.2f})"
        )
    else:
        # Odd case
        middle_idx: int = m // 2
        middle_op = sorted_opinions[middle_idx]
        print(f"Median = middle expert (position {middle_idx + 1}):")
        print(
            f"  {middle_op.expert_id} → {middle_op.opinion} (centroid: {middle_op.opinion.get_centroid():.2f})"
        )

    median = calculator.calculate_median(opinions)

    print(f"\nMedian: Ω({median.lower_bound:.2f}, {median.peak:.2f}, {median.upper_bound:.2f})")
    if m % 2 == 0:
        print(
            f"  ρ (lower) = ({left_op.opinion.lower_bound} + {right_op.opinion.lower_bound}) / 2 = {median.lower_bound:.2f}"
        )
        print(
            f"  ω (peak) = ({left_op.opinion.peak} + {right_op.opinion.peak}) / 2 = {median.peak:.2f}"
        )
        print(
            f"  σ (upper) = ({left_op.opinion.upper_bound} + {right_op.opinion.upper_bound}) / 2 = {median.upper_bound:.2f}"
        )

    # Use the built-in centroid method
    median_centroid: float = median.get_centroid()
    print(
        f"\nMedian centroid: ({median.lower_bound:.2f} + {median.peak:.2f} + {median.upper_bound:.2f}) / 3 = {median_centroid:.2f}"
    )

    # STEP 3: Calculate Best Compromise (ΓΩMean)
    print_section("STEP 3: Best Compromise (ΓΩMean)")

    print("\nFormula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2")

    pi: float = (mean.lower_bound + median.lower_bound) / 2
    phi: float = (mean.peak + median.peak) / 2
    xi: float = (mean.upper_bound + median.upper_bound) / 2

    print(f"\nπ (lower) = ({mean.lower_bound:.2f} + {median.lower_bound:.2f}) / 2 = {pi:.2f}")
    print(f"φ (peak) = ({mean.peak:.2f} + {median.peak:.2f}) / 2 = {phi:.2f}")
    print(f"ξ (upper) = ({mean.upper_bound:.2f} + {median.upper_bound:.2f}) / 2 = {xi:.2f}")

    # Create best compromise object
    best_compromise = FuzzyTriangleNumber(lower_bound=pi, peak=phi, upper_bound=xi)

    # Use the built-in centroid method
    best_compromise_centroid: float = best_compromise.get_centroid()
    print(f"\nBest Compromise: ΓΩMean({pi:.2f}, {phi:.2f}, {xi:.2f})")
    print(
        f"Best compromise centroid: ({pi:.2f} + {phi:.2f} + {xi:.2f}) / 3 = {best_compromise_centroid:.2f}"
    )

    # STEP 4: Calculate Maximum Error (Δmax)
    print_section("STEP 4: Maximum Error (Δmax)")

    print("\nFormula: Δmax = |centroid(Γ) - centroid(Ω)| / 2")
    print("This is the precision indicator (lower is better)")

    max_error: float = abs(mean_centroid - median_centroid) / 2

    print(f"\nMean centroid (Gx): {mean_centroid:.2f}")
    print(f"Median centroid (Gx): {median_centroid:.2f}")
    print(f"Δmax = |{mean_centroid:.2f} - {median_centroid:.2f}| / 2 = {max_error:.2f}")

    # STEP 5: Final Result
    print_section("FINAL RESULT")

    result = calculator.calculate_compromise(opinions)

    print(f"\n{result}")

    # Interpretation
    print_header("INTERPRETATION")

    print(f"\nBest compromise estimate: {best_compromise_centroid:.2f} billion CZK (centroid)")
    print(f"Fuzzy number: ({pi:.2f}, {phi:.2f}, {xi:.2f})")
    print(f"Range: [{pi:.2f}, {xi:.2f}] billion CZK")
    print(f"Precision indicator (Δmax): {max_error:.2f}")

    # Determine agreement level based on max_error thresholds
    agreement_levels = [(1.0, "good"), (3.0, "moderate"), (float("inf"), "low")]
    agreement: str = next(level for threshold, level in agreement_levels if max_error < threshold)

    print(f"Expert agreement: {agreement.upper()}")
    print(
        f"\nThe result suggests that approximately {best_compromise_centroid:.2f} billion CZK"
        f"\nof budget support is the best compromise among all experts."
    )


if __name__ == "__main__":
    main()
