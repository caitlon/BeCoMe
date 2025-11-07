"""
Detailed analysis of PENDLERS CASE.

This script demonstrates step-by-step BeCoMe calculation for the Pendlers case study
with 22 experts (even number) providing Likert scale ratings (0-25-50-75-100)
for cross-border travel policy.
"""

from pathlib import Path

from examples.utils import (
    calculate_agreement_level,
    display_case_header,
    display_step_1_arithmetic_mean,
    display_step_2_median,
    display_step_3_best_compromise,
    display_step_4_max_error,
    load_data_from_txt,
    print_header,
    print_section,
)
from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator
from src.interpreters.likert_interpreter import LikertDecisionInterpreter


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
    data_file = str(Path(__file__).parent / "data" / "pendlers_case.txt")
    opinions, metadata = load_data_from_txt(data_file)

    # Display case header
    display_case_header("PENDLERS CASE", opinions, metadata)

    print("\nLikert scale interpretation:")
    print("  0   = Strongly disagree")
    print("  25  = Rather disagree")
    print("  50  = Neutral")
    print("  75  = Rather agree")
    print("  100 = Strongly agree")

    # STEP 1: Arithmetic Mean (note Likert specifics)
    print("\nNote: For Likert scale, lower = peak = upper (crisp values)")
    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)
    print(f"Mean centroid: {mean_centroid:.2f} (same as peak for crisp values)")

    # STEP 2: Median (with Likert scale display)
    median, median_centroid = display_step_2_median(opinions, calculator, is_likert=True)

    # STEP 3: Best Compromise
    best_compromise, best_compromise_centroid = display_step_3_best_compromise(mean, median)

    # STEP 4: Maximum Error
    max_error = display_step_4_max_error(mean_centroid, median_centroid)

    # STEP 5: Final Result
    print_section("FINAL RESULT")
    result = calculator.calculate_compromise(opinions)
    print(f"\n{result}")

    # Interpretation
    print_header("INTERPRETATION")

    print(f"\nBest compromise estimate: {best_compromise_centroid:.2f} (centroid)")
    print(
        f"Fuzzy number: ({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(f"Precision indicator (Δmax): {max_error:.2f}")

    # Determine agreement level (different thresholds for Likert scale)
    agreement = calculate_agreement_level(max_error, thresholds=(5.0, 10.0))
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
