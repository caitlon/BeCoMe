"""
Detailed BeCoMe analysis of Floods case study.

Demonstrates step-by-step calculation for 13 expert interval estimates
of flood prevention arable land reduction percentage.
"""

from pathlib import Path

from examples.utils.analysis import calculate_agreement_level
from examples.utils.formatting import print_header, print_section
from examples.utils.locales import EN_ANALYSIS, EN_DISPLAY, EN_FORMATTING
from examples.utils.runner import run_analysis
from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator


def main(calculator: BaseAggregationCalculator | None = None) -> None:
    """
    Run detailed BeCoMe analysis for Floods case study.

    :param calculator: Aggregation calculator instance.
                       Defaults to BeCoMeCalculator if not provided.
    """
    if calculator is None:
        calculator = BeCoMeCalculator()

    data_file = str(Path(__file__).parent.parent / "data" / "en" / "floods_case.txt")

    ar = run_analysis(
        data_file=data_file,
        case_title="FLOODS CASE",
        display_labels=EN_DISPLAY,
        formatting_labels=EN_FORMATTING,
        calculator=calculator,
    )

    print_section("FINAL RESULT")
    result = calculator.calculate_compromise(ar.opinions)
    print(f"\n{result}")

    print_header("INTERPRETATION")

    bc = ar.best_compromise
    print(
        f"\nBest compromise estimate: {ar.best_compromise_centroid:.2f}% reduction "
        "of arable land (centroid)"
    )
    print(f"Fuzzy number: ({bc.lower_bound:.2f}, {bc.peak:.2f}, {bc.upper_bound:.2f})")
    print(f"Range: [{bc.lower_bound:.2f}%, {bc.upper_bound:.2f}%]")
    print(f"Precision indicator (Δmax): {ar.max_error:.2f}")

    agreement = calculate_agreement_level(ar.max_error, thresholds=(1.0, 3.0), labels=EN_ANALYSIS)
    print(f"Expert agreement: {agreement.upper()}")

    print("\nNOTE: This case shows highly polarized opinions:")
    print("  - Land owners prefer minimal reduction (0-4%)")
    print("  - Hydrologists/rescue services recommend high reduction (37-50%)")
    print(
        f"  - The BeCoMe method provides a balanced compromise at "
        f"{ar.best_compromise_centroid:.2f}%"
    )
    print(f"  - High max error ({ar.max_error:.2f}) indicates significant disagreement")


if __name__ == "__main__":
    main()
