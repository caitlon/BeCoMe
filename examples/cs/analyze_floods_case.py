"""
Podrobná analýza BeCoMe pro případovou studii Floods.

Demonstruje krok za krokem výpočet pro 13 expertních intervalových odhadů
procenta snížení orné půdy pro protipovodňová opatření.
"""

from pathlib import Path

from examples.cs.utils.analysis import calculate_agreement_level
from examples.cs.utils.display import (
    display_step_1_arithmetic_mean,
    display_step_2_median,
    display_step_3_best_compromise,
    display_step_4_max_error,
)
from examples.cs.utils.formatting import display_case_header, print_header, print_section
from examples.utils.data_loading import load_data_from_txt
from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator


def main(calculator: BaseAggregationCalculator | None = None) -> None:
    """
    Run detailed BeCoMe analysis for Floods case study in Czech.

    :param calculator: Aggregation calculator instance.
                       Defaults to BeCoMeCalculator if not provided.
    """
    if calculator is None:
        calculator = BeCoMeCalculator()

    data_file = str(Path(__file__).parent.parent / "data" / "cs" / "floods_case.txt")
    opinions, metadata = load_data_from_txt(data_file)

    display_case_header("PŘÍPAD POVODNĚ", opinions, metadata)

    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator)

    median, median_centroid = display_step_2_median(opinions, calculator)

    best_compromise, best_compromise_centroid = display_step_3_best_compromise(mean, median)

    max_error = display_step_4_max_error(mean_centroid, median_centroid)

    print_section("KONEČNÝ VÝSLEDEK")
    result = calculator.calculate_compromise(opinions)
    m = len(opinions)
    parity = "sudý" if m % 2 == 0 else "lichý"
    print(f"\nVýsledek BeCoMe ({m} expertů, {parity}):")
    print(
        f"  Nejlepší kompromis: ({result.best_compromise.lower_bound:.2f}, "
        f"{result.best_compromise.peak:.2f}, {result.best_compromise.upper_bound:.2f})"
    )
    print(
        f"  Aritmetický průměr: ({result.arithmetic_mean.lower_bound:.2f}, "
        f"{result.arithmetic_mean.peak:.2f}, {result.arithmetic_mean.upper_bound:.2f})"
    )
    print(
        f"  Medián: ({result.median.lower_bound:.2f}, "
        f"{result.median.peak:.2f}, {result.median.upper_bound:.2f})"
    )
    print(f"  Maximální chyba: {result.max_error:.2f}")

    print_header("INTERPRETACE")

    print(
        f"\nOdhad nejlepšího kompromisu: {best_compromise_centroid:.2f}% snížení "
        "orné půdy (těžiště)"
    )
    print(
        f"Fuzzy číslo: ({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(f"Rozsah: [{best_compromise.lower_bound:.2f}%, {best_compromise.upper_bound:.2f}%]")
    print(f"Ukazatel přesnosti (Δmax): {max_error:.2f}")

    agreement = calculate_agreement_level(max_error, thresholds=(1.0, 3.0))
    print(f"Shoda expertů: {agreement.upper()}")

    print("\nPOZNÁMKA: Tento případ ukazuje silně polarizované názory:")
    print("  - Majitelé půdy preferují minimální snížení (0-4%)")
    print("  - Hydrologové/záchranáři doporučují vysoké snížení (37-50%)")
    print(f"  - Metoda BeCoMe poskytuje vyvážený kompromis na {best_compromise_centroid:.2f}%")
    print(f"  - Vysoká maximální chyba ({max_error:.2f}) indikuje významnou neshodu")


if __name__ == "__main__":
    main()
