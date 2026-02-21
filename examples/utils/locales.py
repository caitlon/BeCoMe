"""Pre-built locale instances for English and Czech."""
# ruff: noqa: RUF001

from examples.utils.labels import AnalysisLabels, DisplayLabels, FormattingLabels

# ---------------------------------------------------------------------------
# English
# ---------------------------------------------------------------------------

EN_DISPLAY = DisplayLabels(
    # Shared component positions
    lower_pos="lower",
    peak_pos="peak",
    upper_pos="upper",
    # Step 1
    step_1_title="STEP 1: Arithmetic Mean (Gamma)",
    formula_step_1="Formula: α = (1/M) x Σ(Ak), γ = (1/M) x Σ(Ck), β = (1/M) x Σ(Bk)",
    formula_where="Where: α = lower bound, γ = peak, β = upper bound",
    sum_lower_label="Sum of lower bounds",
    sum_peaks_label="Sum of peaks",
    sum_upper_label="Sum of upper bounds",
    arithmetic_mean_label="Arithmetic Mean",
    mean_centroid_name="Mean centroid",
    # Step 2 — detail
    expert_count_template="Number of experts is {parity} (M={m})",
    even_upper="EVEN",
    odd_upper="ODD",
    median_even_template="Median = average of {left}th and {right}th experts:",
    median_odd_template="Median = middle expert (position {pos}):",
    centroid_word="centroid",
    # Step 2 — main
    step_2_title="STEP 2: Median (Omega)",
    sorting_by_value="Sorting experts by value (centroid)...",
    sorting_by_centroid="Sorting experts by centroid...",
    median_result_label="Median",
    all_components_label="All components",
    from_middle_expert="from middle expert",
    median_centroid_name="Median centroid",
    # Step 3
    step_3_title="STEP 3: Best Compromise (ΓΩMean)",
    formula_step_3="Formula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2",
    best_compromise_label="Best Compromise",
    bc_centroid_label="Best compromise centroid",
    # Step 4
    step_4_title="STEP 4: Maximum Error (Δmax)",
    formula_step_4="Formula: Δmax = |centroid(Γ) - centroid(Ω)| / 2",
    precision_note="This is the precision indicator (lower is better)",
    mean_centroid_gx="Mean centroid (Gx)",
    median_centroid_gx="Median centroid (Gx)",
)

EN_FORMATTING = FormattingLabels(
    detailed_analysis="DETAILED ANALYSIS",
    case_label="Case",
    description_label="Description",
    num_experts_label="Number of experts",
    even_label="even",
    odd_label="odd",
    default_centroid_name="Centroid",
    not_available_label="N/A",
)

EN_ANALYSIS = AnalysisLabels(good="good", moderate="moderate", low="low")

# ---------------------------------------------------------------------------
# Czech
# ---------------------------------------------------------------------------

CS_DISPLAY = DisplayLabels(
    # Shared component positions
    lower_pos="dolní hranice",
    peak_pos="vrchol",
    upper_pos="horní hranice",
    # Step 1
    step_1_title="KROK 1: Aritmetický průměr (Γ)",
    formula_step_1="Vzorec: α = (1/M) x Σ(Ak), γ = (1/M) x Σ(Ck), β = (1/M) x Σ(Bk)",
    formula_where="Kde: α = dolní hranice, γ = vrchol, β = horní hranice",
    sum_lower_label="Součet dolních hranic",
    sum_peaks_label="Součet vrcholů",
    sum_upper_label="Součet horních hranic",
    arithmetic_mean_label="Aritmetický průměr",
    mean_centroid_name="Těžiště průměru",
    # Step 2 — detail
    expert_count_template="Počet expertů je {parity} (M={m})",
    even_upper="SUDÝ",
    odd_upper="LICHÝ",
    median_even_template="Medián = průměr {left}. a {right}. experta:",
    median_odd_template="Medián = střední expert (pozice {pos}):",
    centroid_word="těžiště",
    # Step 2 — main
    step_2_title="KROK 2: Medián (Ω)",
    sorting_by_value="Řazení expertů podle hodnoty (těžiště)...",
    sorting_by_centroid="Řazení expertů podle těžiště...",
    median_result_label="Medián",
    all_components_label="Všechny složky",
    from_middle_expert="od středního experta",
    median_centroid_name="Těžiště mediánu",
    # Step 3
    step_3_title="KROK 3: Nejlepší kompromis (ΓΩMean)",
    formula_step_3="Vzorec: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2",
    best_compromise_label="Nejlepší kompromis",
    bc_centroid_label="Těžiště nejlepšího kompromisu",
    # Step 4
    step_4_title="KROK 4: Maximální chyba (Δmax)",
    formula_step_4="Vzorec: Δmax = |těžiště(Γ) - těžiště(Ω)| / 2",
    precision_note="Ukazatel přesnosti (nižší = lepší)",
    mean_centroid_gx="Těžiště průměru (Gx)",
    median_centroid_gx="Těžiště mediánu (Gx)",
)

CS_FORMATTING = FormattingLabels(
    detailed_analysis="PODROBNÁ ANALÝZA",
    case_label="Případ",
    description_label="Popis",
    num_experts_label="Počet expertů",
    even_label="sudý",
    odd_label="lichý",
    default_centroid_name="Těžiště",
    not_available_label="Nedostupné",
)

CS_ANALYSIS = AnalysisLabels(good="vysoká", moderate="střední", low="nízká")
