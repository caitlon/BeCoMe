"""Localized labels for rendered result-export reports (English and Czech).

The Greek method symbols and Czech diacritics live here as string literals, so
both the PDF (rendered with the bundled DejaVu Sans font) and the UTF-8 CSV
carry the same wording the web UI shows.
"""

from dataclasses import dataclass

from api.services.export.data import ReportLang


@dataclass(frozen=True, slots=True)
class ResultLabels:
    """Static text used in a rendered report, in a single language."""

    report_title: str
    description: str
    scale: str
    generated_at: str
    experts: str
    results_heading: str
    best_compromise: str
    arithmetic_mean: str
    median: str
    max_error: str
    likert_decision: str
    chart_heading: str
    membership_axis: str
    opinions_heading: str
    col_expert: str
    col_position: str
    col_lower: str
    col_peak: str
    col_upper: str
    col_centroid: str
    legend_mean: str
    legend_median: str
    legend_best: str
    likert_decisions: dict[int, str]


_EN = ResultLabels(
    report_title="BeCoMe results report",
    description="Description",
    scale="Scale",
    generated_at="Generated at",
    experts="Experts",
    results_heading="Aggregated results",
    best_compromise="Best Compromise (ΓΩMean)",
    arithmetic_mean="Arithmetic Mean (Γ)",
    median="Median (Ω)",
    max_error="Max Error (Δmax)",
    likert_decision="Likert decision",
    chart_heading="Fuzzy triangle visualization",
    membership_axis="Membership",
    opinions_heading="Expert Opinions",
    col_expert="Expert",
    col_position="Position",
    col_lower="Lower",
    col_peak="Peak",
    col_upper="Upper",
    col_centroid="Centroid",
    legend_mean="Arithmetic mean",
    legend_median="Median",
    legend_best="Best compromise",
    likert_decisions={
        0: "Strongly disagree",
        25: "Rather disagree",
        50: "Neutral",
        75: "Rather agree",
        100: "Strongly agree",
    },
)

_CS = ResultLabels(
    report_title="Zpráva o výsledcích BeCoMe",
    description="Popis",
    scale="Škála",
    generated_at="Vygenerováno",
    experts="Experti",
    results_heading="Agregované výsledky",
    best_compromise="Nejlepší kompromis (ΓΩMean)",
    arithmetic_mean="Aritmetický průměr (Γ)",
    median="Medián (Ω)",
    max_error="Max. chyba (Δmax)",
    likert_decision="Likertovo rozhodnutí",
    chart_heading="Vizualizace fuzzy trojúhelníku",
    membership_axis="Příslušnost",
    opinions_heading="Expertní názory",
    col_expert="Expert",
    col_position="Pozice",
    col_lower="Dolní",
    col_peak="Vrchol",
    col_upper="Horní",
    col_centroid="Těžiště",
    legend_mean="Aritmetický průměr",
    legend_median="Medián",
    legend_best="Nejlepší kompromis",
    likert_decisions={
        0: "Rozhodně nesouhlasím",
        25: "Spíše nesouhlasím",
        50: "Neutrální",
        75: "Spíše souhlasím",
        100: "Rozhodně souhlasím",
    },
)


def get_labels(lang: ReportLang) -> ResultLabels:
    """Return the report labels for the requested language.

    :param lang: Target report language.
    :return: ResultLabels for Czech when requested, English otherwise.
    """
    return _CS if lang == ReportLang.CS else _EN
