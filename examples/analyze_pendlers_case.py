"""
Detailed analysis of PENDLERS CASE.

This script demonstrates step-by-step BeCoMe calculation for the Pendlers case study
with 22 experts (even number) providing Likert scale ratings (0-25-50-75-100)
for cross-border travel policy.
"""

# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001

from pathlib import Path

from examples.utils import load_data_from_txt, print_header, print_section
from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator
from src.interpreters.likert_interpreter import LikertDecisionInterpreter
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


def main(calculator: BaseAggregationCalculator | None = None) -> None:
    """
    Run detailed analysis of Pendlers case.

    This function demonstrates Dependency Injection (DI) pattern from SOLID
    principles. Instead of creating a calculator directly, it accepts one as
    a parameter, depending on the abstraction (BaseAggregationCalculator)
    rather than the concrete implementation (BeCoMeCalculator).

    Args:
        calculator: Aggregation calculator to use for analysis.
                   If None, defaults to BeCoMeCalculator().
                   This allows for easy testing and flexibility.

    Example:
        >>> # Use default calculator
        >>> main()
        >>>
        >>> # Inject custom calculator for testing
        >>> custom_calc = BeCoMeCalculator()
        >>> main(calculator=custom_calc)
    """
    # Dependency Injection: use provided calculator or create default
    if calculator is None:
        calculator = BeCoMeCalculator()

    # Load data from text file
    data_file: str = str(Path(__file__).parent / "data" / "pendlers_case.txt")
    opinions: list[ExpertOpinion]
    metadata: dict[str, str]
    opinions, metadata = load_data_from_txt(data_file)

    # Display case information
    print_header("PENDLERS CASE - DETAILED ANALYSIS")

    print(f"\nCase: {metadata['case']}")
    print(f"Description: {metadata['description']}")
    print(f"Number of experts: {len(opinions)} ({'even' if len(opinions) % 2 == 0 else 'odd'})")

    print("\nLikert scale interpretation:")
    print("  0   = Strongly disagree")
    print("  25  = Rather disagree")
    print("  50  = Neutral")
    print("  75  = Rather agree")
    print("  100 = Strongly agree")

    # STEP 1: Calculate Arithmetic Mean (Gamma)
    print_section("STEP 1: Arithmetic Mean (Gamma)")

    print("\nFormula: α = (1/M) × Σ(Ak), γ = (1/M) × Σ(Ck), β = (1/M) × Σ(Bk)")
    print("Note: For Likert scale, lower = peak = upper (crisp values)")

    # Use calculator method instead of manual calculation
    mean = calculator.calculate_arithmetic_mean(opinions)
    m: int = len(opinions)

    # Calculate sum for display purposes (derived from mean)
    sum_values: float = mean.peak * m

    print(f"\nSum of all values: {sum_values}")

    print(f"\nArithmetic Mean: Γ({mean.lower_bound:.2f}, {mean.peak:.2f}, {mean.upper_bound:.2f})")
    print(f"  All components = {sum_values} / {m} = {mean.peak:.2f}")

    mean_centroid: float = mean.centroid
    print(f"\nMean centroid: {mean_centroid:.2f} (same as peak for crisp values)")

    # STEP 2: Calculate Median (Omega)
    print_section("STEP 2: Median (Omega)")

    print("\nSorting experts by value (centroid)...")
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
        print(f"  {left_idx + 1}th: {left_op.expert_id} → {int(left_op.opinion.peak)}")
        print(f"  {right_idx + 1}th: {right_op.expert_id} → {int(right_op.opinion.peak)}")
    else:
        # Odd case
        middle_idx: int = m // 2
        middle_op = sorted_opinions[middle_idx]
        print(f"Median = middle expert (position {middle_idx + 1}):")
        print(f"  {middle_op.expert_id} → {int(middle_op.opinion.peak)}")

    median = calculator.calculate_median(opinions)

    print(f"\nMedian: Ω({median.lower_bound:.2f}, {median.peak:.2f}, {median.upper_bound:.2f})")
    if m % 2 == 0:
        print(
            f"  All components = ({int(left_op.opinion.peak)} + {int(right_op.opinion.peak)}) / 2 = {median.peak:.2f}"
        )

    median_centroid: float = median.centroid
    print(f"\nMedian centroid: {median_centroid:.2f}")

    # STEP 3: Calculate Best Compromise (ΓΩMean)
    print_section("STEP 3: Best Compromise (ΓΩMean)")

    print("\nFormula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2")

    result = calculator.calculate_compromise(opinions)
    best_compromise: FuzzyTriangleNumber = result.best_compromise

    print(
        f"\nπ (lower) = ({mean.lower_bound:.2f} + {median.lower_bound:.2f}) / 2 = "
        f"{best_compromise.lower_bound:.2f}"
    )
    print(f"φ (peak) = ({mean.peak:.2f} + {median.peak:.2f}) / 2 = {best_compromise.peak:.2f}")
    print(
        f"ξ (upper) = ({mean.upper_bound:.2f} + {median.upper_bound:.2f}) / 2 = "
        f"{best_compromise.upper_bound:.2f}"
    )

    # Use the built-in centroid method
    best_compromise_centroid: float = best_compromise.centroid
    print(
        f"\nBest Compromise: ΓΩMean({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(f"Best compromise centroid: {best_compromise_centroid:.2f}")

    # STEP 4: Calculate Maximum Error (Δmax)
    print_section("STEP 4: Maximum Error (Δmax)")

    print("\nFormula: Δmax = |centroid(Γ) - centroid(Ω)| / 2")
    print("This is the precision indicator (lower is better)")

    max_error: float = result.max_error

    print(f"\nMean centroid (Gx): {mean_centroid:.2f}")
    print(f"Median centroid (Gx): {median_centroid:.2f}")
    print(f"Δmax = |{mean_centroid:.2f} - {median_centroid:.2f}| / 2 = {max_error:.2f}")

    # STEP 5: Final Result
    print_section("FINAL RESULT")

    print(f"\n{result}")

    # Interpretation
    print_header("INTERPRETATION")

    print(f"\nBest compromise estimate: {best_compromise_centroid:.2f} (centroid)")
    print(
        "Fuzzy number: "
        f"({best_compromise.lower_bound:.2f}, {best_compromise.peak:.2f}, "
        f"{best_compromise.upper_bound:.2f})"
    )
    print(f"Precision indicator (Δmax): {max_error:.2f}")

    # Determine agreement level based on max_error thresholds
    agreement_levels = [(5.0, "good"), (10.0, "moderate"), (float("inf"), "low")]
    agreement: str = next(level for threshold, level in agreement_levels if max_error < threshold)

    print(f"Expert agreement: {agreement.upper()}")

    # Use LikertDecisionInterpreter for clean, OOP-based interpretation
    # This demonstrates Single Responsibility Principle: interpretation
    # logic is encapsulated in a dedicated class
    interpreter = LikertDecisionInterpreter()
    decision = interpreter.interpret(best_compromise)

    print(f"Closest Likert value: {decision.likert_value}")
    print(f"\nDECISION (based on centroid {best_compromise_centroid:.2f}):")
    print(f"  {decision.decision_text.upper()}")
    print(f"\nRecommendation: {decision.recommendation}")


if __name__ == "__main__":
    main()
