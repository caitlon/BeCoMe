"""
Detailed BeCoMe analysis of Budget case study.

Demonstrates step-by-step calculation for 22 expert interval estimates
of COVID-19 pandemic budget support.
"""

from pathlib import Path

from examples.utils.analysis import calculate_agreement_level
from examples.utils.data_loading import load_data_from_txt
from examples.utils.display import (
    display_step_1_arithmetic_mean,
    display_step_2_median,
    display_step_3_best_compromise,
    display_step_4_max_error,
)
from examples.utils.formatting import display_case_header, print_header, print_section
from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator


def main(calculator: BaseAggregationCalculator | None = None) -> None:
    """
    Run detailed BeCoMe analysis for Budget case study.

    :param calculator: Aggregation calculator instance.
                       Defaults to BeCoMeCalculator if not provided.

    >>> main()  # Uses default BeCoMeCalculator
    """
    if calculator is None:
        calculator = BeCoMeCalculator()

    data_file = str(Path(__file__).parent / "data" / "budget_case.txt")
    opinions, metadata = load_data_from_txt(data_file)

    display_case_header("BUDGET CASE", opinions, metadata)

    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)

    median, median_centroid = display_step_2_median(opinions, calculator)

    best_compromise, best_compromise_centroid = display_step_3_best_compromise(mean, median)

    max_error = display_step_4_max_error(mean_centroid, median_centroid)

    print_section("FINAL RESULT")
    result = calculator.calculate_compromise(opinions)
    print(f"\n{result}")

    print_header("INTERPRETATION")

    print(f"\nBest compromise estimate: {best_compromise_centroid:.2f} billion CZK (centroid)")
    print(
        f"Fuzzy number: ({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(
        f"Range: [{best_compromise.lower_bound:.2f}, {best_compromise.upper_bound:.2f}] billion CZK"
    )
    print(f"Precision indicator (Δmax): {max_error:.2f}")

    agreement = calculate_agreement_level(max_error, thresholds=(1.0, 3.0))
    print(f"Expert agreement: {agreement.upper()}")

    print(
        f"\nThe result suggests that approximately {best_compromise_centroid:.2f} billion CZK"
        f"\nof budget support is the best compromise among all experts."
    )


if __name__ == "__main__":
    main()
