"""
Detailed analysis of BUDGET CASE.

This script demonstrates step-by-step BeCoMe calculation for the Budget case study
with 22 experts (even number) providing interval estimates for COVID-19 pandemic
budget support.
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


def main(calculator: BaseAggregationCalculator | None = None) -> None:
    """
    Run detailed analysis of Budget case.

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
    data_file = str(Path(__file__).parent / "data" / "budget_case.txt")
    opinions, metadata = load_data_from_txt(data_file)

    # Display case header
    display_case_header("BUDGET CASE", opinions, metadata)

    # STEP 1: Arithmetic Mean
    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)

    # STEP 2: Median
    median, median_centroid = display_step_2_median(opinions, calculator)

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

    print(f"\nBest compromise estimate: {best_compromise_centroid:.2f} billion CZK (centroid)")
    print(
        f"Fuzzy number: ({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(
        f"Range: [{best_compromise.lower_bound:.2f}, {best_compromise.upper_bound:.2f}] billion CZK"
    )
    print(f"Precision indicator (Δmax): {max_error:.2f}")

    # Determine agreement level
    agreement = calculate_agreement_level(max_error, thresholds=(1.0, 3.0))
    print(f"Expert agreement: {agreement.upper()}")

    print(
        f"\nThe result suggests that approximately {best_compromise_centroid:.2f} billion CZK"
        f"\nof budget support is the best compromise among all experts."
    )


if __name__ == "__main__":
    main()
