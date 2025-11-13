"""
Detailed BeCoMe analysis of Pendlers case study.

Demonstrates step-by-step calculation for 22 expert Likert scale ratings (0-25-50-75-100) for cross-border travel policy.
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
    Run detailed BeCoMe analysis for Pendlers case study.

    :param calculator: Aggregation calculator instance.
                       Defaults to BeCoMeCalculator if not provided.

    >>> main()  # Uses default BeCoMeCalculator
    """
    if calculator is None:
        calculator = BeCoMeCalculator()

    data_file = str(Path(__file__).parent / "data" / "pendlers_case.txt")
    opinions, metadata = load_data_from_txt(data_file)

    display_case_header("PENDLERS CASE", opinions, metadata)

    print("\nLikert scale interpretation:")
    print("  0   = Strongly disagree")
    print("  25  = Rather disagree")
    print("  50  = Neutral")
    print("  75  = Rather agree")
    print("  100 = Strongly agree")

    print("\nNote: For Likert scale, lower = peak = upper (crisp values)")
    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)
    print(f"Mean centroid: {mean_centroid:.2f} (same as peak for crisp values)")

    median, median_centroid = display_step_2_median(opinions, calculator, is_likert=True)

    best_compromise, best_compromise_centroid = display_step_3_best_compromise(mean, median)

    max_error = display_step_4_max_error(mean_centroid, median_centroid)

    print_section("FINAL RESULT")
    result = calculator.calculate_compromise(opinions)
    print(f"\n{result}")

    print_header("INTERPRETATION")

    print(f"\nBest compromise estimate: {best_compromise_centroid:.2f} (centroid)")
    print(
        f"Fuzzy number: ({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(f"Precision indicator (Δmax): {max_error:.2f}")

    agreement = calculate_agreement_level(max_error, thresholds=(5.0, 10.0))
    print(f"Expert agreement: {agreement.upper()}")

    interpreter = LikertDecisionInterpreter()
    decision = interpreter.interpret(best_compromise)

    print(f"Closest Likert value: {decision.likert_value}")
    print(f"\nDECISION (based on centroid {best_compromise_centroid:.2f}):")
    print(f"  {decision.decision_text.upper()}")
    print(f"\nRecommendation: {decision.recommendation}")


if __name__ == "__main__":
    main()
