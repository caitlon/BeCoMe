"""
Podrobná analýza BeCoMe pro případovou studii Pendlers.

Demonstruje krok za krokem výpočet pro 22 expertních hodnocení
na Likertově škále (0-25-50-75-100) pro politiku přeshraničního cestování.
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
from examples.utils.locales import CS_ANALYSIS, CS_DISPLAY, CS_FORMATTING
from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator
from src.interpreters.likert_interpreter import LikertDecisionInterpreter


def main(calculator: BaseAggregationCalculator | None = None) -> None:
    """
    Run detailed BeCoMe analysis for Pendlers case study in Czech.

    :param calculator: Aggregation calculator instance.
                       Defaults to BeCoMeCalculator if not provided.
    """
    if calculator is None:
        calculator = BeCoMeCalculator()

    data_file = str(Path(__file__).parent.parent / "data" / "cs" / "pendlers_case.txt")
    opinions, metadata = load_data_from_txt(data_file)

    display_case_header("PŘÍPAD PENDLEŘI", opinions, metadata, CS_FORMATTING)

    print("\nInterpretace Likertovy škály:")
    print("  0   = Rozhodně nesouhlasím")
    print("  25  = Spíše nesouhlasím")
    print("  50  = Neutrální")
    print("  75  = Spíše souhlasím")
    print("  100 = Rozhodně souhlasím")

    print("\nPoznámka: Pro Likertovu škálu platí: dolní = vrchol = horní (přesné hodnoty)")
    mean, mean_centroid = display_step_1_arithmetic_mean(opinions, calculator, CS_DISPLAY)
    print(f"Těžiště průměru: {mean_centroid:.2f} (stejné jako vrchol pro přesné hodnoty)")

    median, median_centroid = display_step_2_median(
        opinions, calculator, is_likert=True, labels=CS_DISPLAY
    )

    best_compromise, bc_centroid = display_step_3_best_compromise(mean, median, CS_DISPLAY)

    max_error = display_step_4_max_error(mean_centroid, median_centroid, CS_DISPLAY)

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

    print(f"\nOdhad nejlepšího kompromisu: {bc_centroid:.2f} (těžiště)")
    print(
        f"Fuzzy číslo: ({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(f"Ukazatel přesnosti (Δmax): {max_error:.2f}")

    agreement = calculate_agreement_level(max_error, thresholds=(5.0, 10.0), labels=CS_ANALYSIS)
    print(f"Shoda expertů: {agreement.upper()}")

    interpreter = LikertDecisionInterpreter()
    decision = interpreter.interpret(best_compromise)

    decision_cs = {
        0: "Rozhodně nesouhlasím",
        25: "Spíše nesouhlasím",
        50: "Neutrální",
        75: "Spíše souhlasím",
        100: "Rozhodně souhlasím",
    }
    recommendation_cs = {
        0: "Politika není doporučena a měla by být zamítnuta",
        25: "Politika vyžaduje významnou revizi před zvážením",
        50: "Politika vyžaduje další analýzu a vstup zainteresovaných stran",
        75: "Politika je doporučena s drobnými úpravami",
        100: "Politika je silně doporučena k implementaci",
    }

    print(f"Nejbližší hodnota Likertovy škály: {decision.likert_value}")
    print(f"\nROZHODNUTÍ (na základě těžiště {bc_centroid:.2f}):")
    print(f"  {decision_cs.get(decision.likert_value, decision.decision_text).upper()}")
    print(f"\nDoporučení: {recommendation_cs.get(decision.likert_value, decision.recommendation)}")


if __name__ == "__main__":
    main()
