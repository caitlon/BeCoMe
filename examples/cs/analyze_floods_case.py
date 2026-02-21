"""
Podrobná analýza BeCoMe pro případovou studii Floods.

Demonstruje krok za krokem výpočet pro 13 expertních intervalových odhadů
procenta snížení orné půdy pro protipovodňová opatření.
"""

from pathlib import Path

from examples.utils.analysis import calculate_agreement_level
from examples.utils.formatting import print_header, print_section
from examples.utils.locales import CS_ANALYSIS, CS_DISPLAY, CS_FORMATTING
from examples.utils.runner import run_analysis
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

    ar = run_analysis(
        data_file=data_file,
        case_title="PŘÍPAD POVODNĚ",
        display_labels=CS_DISPLAY,
        formatting_labels=CS_FORMATTING,
        calculator=calculator,
    )

    print_section("KONEČNÝ VÝSLEDEK")
    result = calculator.calculate_compromise(ar.opinions)
    m = len(ar.opinions)
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

    bc = ar.best_compromise
    print(
        f"\nOdhad nejlepšího kompromisu: {ar.best_compromise_centroid:.2f}% snížení "
        "orné půdy (těžiště)"
    )
    print(f"Fuzzy číslo: ({bc.lower_bound:.2f}, {bc.peak:.2f}, {bc.upper_bound:.2f})")
    print(f"Rozsah: [{bc.lower_bound:.2f}%, {bc.upper_bound:.2f}%]")
    print(f"Ukazatel přesnosti (Δmax): {ar.max_error:.2f}")

    agreement = calculate_agreement_level(ar.max_error, thresholds=(1.0, 3.0), labels=CS_ANALYSIS)
    print(f"Shoda expertů: {agreement.upper()}")

    print("\nPOZNÁMKA: Tento případ ukazuje silně polarizované názory:")
    print("  - Majitelé půdy preferují minimální snížení (0-4%)")
    print("  - Hydrologové/záchranáři doporučují vysoké snížení (37-50%)")
    print(f"  - Metoda BeCoMe poskytuje vyvážený kompromis na {ar.best_compromise_centroid:.2f}%")
    print(f"  - Vysoká maximální chyba ({ar.max_error:.2f}) indikuje významnou neshodu")


if __name__ == "__main__":
    main()
