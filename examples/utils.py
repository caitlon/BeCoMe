"""
Utility functions for examples.

This module provides helper functions for loading and processing
data for BeCoMe examples.
"""
# ignore ruff rule for mathematical symbols
# ruff: noqa: RUF001

from pathlib import Path

from src.calculators.base_calculator import BaseAggregationCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


def load_data_from_txt(filepath: str) -> tuple[list[ExpertOpinion], dict[str, str]]:
    """
    Load expert opinions from a text file.

    The text file should have the following format:
        CASE: CaseName
        DESCRIPTION: Case description
        EXPERTS: N

        # Format: ExpertID | Lower | Peak | Upper
        Expert1 | 10 | 15 | 20
        Expert2 | 12 | 18 | 25
        ...

    Args:
        filepath: Path to the text file

    Returns:
        Tuple of (list of ExpertOpinion objects, metadata dict)
        Metadata dict contains: 'case', 'description', 'num_experts'

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is invalid
    """
    file_path = Path(filepath)

    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    metadata: dict[str, str] = {}
    opinions: list[ExpertOpinion] = []

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comment lines
            if not line or line.startswith("#"):
                continue

            # Parse metadata
            if line.startswith("CASE:"):
                metadata["case"] = line.split("CASE:")[1].strip()
            elif line.startswith("DESCRIPTION:"):
                metadata["description"] = line.split("DESCRIPTION:")[1].strip()
            elif line.startswith("EXPERTS:"):
                metadata["num_experts"] = line.split("EXPERTS:")[1].strip()
            elif "|" in line:
                # Parse expert opinion line
                parts: list[str] = [part.strip() for part in line.split("|")]

                if len(parts) != 4:
                    raise ValueError(
                        f"Invalid line format (expected 4 parts): {line}\n"
                        f"Expected format: ExpertID | Lower | Peak | Upper"
                    )

                expert_id: str = parts[0]
                try:
                    lower: float = float(parts[1])
                    peak: float = float(parts[2])
                    upper: float = float(parts[3])
                except ValueError as e:
                    raise ValueError(f"Invalid numeric values in line: {line}") from e

                # Create fuzzy number and expert opinion
                fuzzy_number = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)
                opinion = ExpertOpinion(expert_id=expert_id, opinion=fuzzy_number)
                opinions.append(opinion)

    # Validate that we loaded the expected number of experts
    if "num_experts" in metadata:
        expected_count: int = int(metadata["num_experts"])
        actual_count: int = len(opinions)
        if actual_count != expected_count:
            raise ValueError(f"Expected {expected_count} experts but loaded {actual_count}")

    return opinions, metadata


def print_header(title: str, width: int = 60) -> None:
    """
    Print a formatted header.

    Args:
        title: Title text to display
        width: Total width of the header
    """
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def print_section(title: str, width: int = 60) -> None:
    """
    Print a formatted section divider.

    Args:
        title: Section title
        width: Total width of the divider
    """
    padding: int = (width - len(title) - 2) // 2
    print("\n" + "-" * padding + f" {title} " + "-" * padding)


def display_case_header(
    case_name: str,
    opinions: list[ExpertOpinion],
    metadata: dict[str, str],
) -> None:
    """
    Display case study header with metadata.

    Args:
        case_name: Name of the case study (e.g., "BUDGET CASE")
        opinions: List of expert opinions
        metadata: Metadata dictionary with case info
    """
    print_header(f"{case_name} - DETAILED ANALYSIS")
    print(f"\nCase: {metadata['case']}")
    print(f"Description: {metadata['description']}")
    print(f"Number of experts: {len(opinions)} ({'even' if len(opinions) % 2 == 0 else 'odd'})")


def display_centroid(fuzzy_number: FuzzyTriangleNumber, name: str = "Centroid") -> None:
    """
    Display centroid calculation in standard format.

    Args:
        fuzzy_number: The fuzzy number to display centroid for
        name: Label for the centroid (e.g., "Mean centroid")
    """

    centroid = fuzzy_number.centroid
    print(
        f"\n{name}: ({fuzzy_number.lower_bound:.2f} + "
        f"{fuzzy_number.peak:.2f} + {fuzzy_number.upper_bound:.2f}) / 3 = "
        f"{centroid:.2f}"
    )


def display_step_1_arithmetic_mean(
    opinions: list[ExpertOpinion], calculator: BaseAggregationCalculator
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 1: Arithmetic Mean calculation with detailed output.

    Args:
        opinions: List of expert opinions
        calculator: Calculator instance to use

    Returns:
        Tuple of (mean, mean_centroid)
    """

    print_section("STEP 1: Arithmetic Mean (Gamma)")

    print("\nFormula: α = (1/M) × Σ(Ak), γ = (1/M) × Σ(Ck), β = (1/M) × Σ(Bk)")
    print("Where: α = lower bound, γ = peak, β = upper bound")

    mean = calculator.calculate_arithmetic_mean(opinions)
    m = len(opinions)

    # Calculate sums for display purposes
    sum_lower = mean.lower_bound * m
    sum_peak = mean.peak * m
    sum_upper = mean.upper_bound * m

    print(f"\nSum of lower bounds: {sum_lower}")
    print(f"Sum of peaks: {sum_peak}")
    print(f"Sum of upper bounds: {sum_upper}")

    print(f"\nArithmetic Mean: Γ({mean.lower_bound:.2f}, {mean.peak:.2f}, {mean.upper_bound:.2f})")
    print(f"  α (lower) = {sum_lower} / {m} = {mean.lower_bound:.2f}")
    print(f"  γ (peak) = {sum_peak} / {m} = {mean.peak:.2f}")
    print(f"  β (upper) = {sum_upper} / {m} = {mean.upper_bound:.2f}")

    mean_centroid = mean.centroid
    display_centroid(mean, "Mean centroid")

    return mean, mean_centroid


def display_median_calculation_details(
    sorted_opinions: list[ExpertOpinion], m: int, is_likert: bool = False
) -> None:
    """
    Display median calculation details for odd or even number of experts.

    Args:
        sorted_opinions: Opinions sorted by centroid
        m: Number of experts
        is_likert: Whether to display as Likert scale values
    """
    print(f"\nNumber of experts is {'EVEN' if m % 2 == 0 else 'ODD'} (M={m})")

    if m % 2 == 0:
        # Even case
        n = m // 2
        left_idx = n - 1
        right_idx = n

        left_op = sorted_opinions[left_idx]
        right_op = sorted_opinions[right_idx]

        print(f"Median = average of {left_idx + 1}th and {right_idx + 1}th experts:")
        if is_likert:
            print(f"  {left_idx + 1}th: {left_op.expert_id} → {int(left_op.opinion.peak)}")
            print(f"  {right_idx + 1}th: {right_op.expert_id} → {int(right_op.opinion.peak)}")
        else:
            print(
                f"  {left_idx + 1}th: {left_op.expert_id} → {left_op.opinion} "
                f"(centroid: {left_op.opinion.centroid:.2f})"
            )
            print(
                f"  {right_idx + 1}th: {right_op.expert_id} → {right_op.opinion} "
                f"(centroid: {right_op.opinion.centroid:.2f})"
            )
    else:
        # Odd case
        middle_idx = m // 2
        middle_op = sorted_opinions[middle_idx]
        print(f"Median = middle expert (position {middle_idx + 1}):")
        if is_likert:
            print(f"  {middle_op.expert_id} → {int(middle_op.opinion.peak)}")
        else:
            print(
                f"  {middle_op.expert_id} → {middle_op.opinion} "
                f"(centroid: {middle_op.opinion.centroid:.2f})"
            )


def display_step_2_median(
    opinions: list[ExpertOpinion], calculator: BaseAggregationCalculator, is_likert: bool = False
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 2: Median calculation with detailed output.

    Args:
        opinions: List of expert opinions
        calculator: Calculator instance to use
        is_likert: Whether this is Likert scale data

    Returns:
        Tuple of (median, median_centroid)
    """
    print_section("STEP 2: Median (Omega)")

    if is_likert:
        print("\nSorting experts by value (centroid)...")
    else:
        print("\nSorting experts by centroid...")

    sorted_opinions = calculator.sort_by_centroid(opinions)
    m = len(sorted_opinions)

    display_median_calculation_details(sorted_opinions, m, is_likert)

    median = calculator.calculate_median(opinions)

    print(f"\nMedian: Ω({median.lower_bound:.2f}, {median.peak:.2f}, {median.upper_bound:.2f})")

    # Display component calculation based on odd/even
    if m % 2 == 0:
        n = m // 2
        left_op = sorted_opinions[n - 1]
        right_op = sorted_opinions[n]

        if is_likert:
            print(
                f"  All components = ({int(left_op.opinion.peak)} + "
                f"{int(right_op.opinion.peak)}) / 2 = {median.peak:.2f}"
            )
        else:
            print(
                f"  ρ (lower) = ({left_op.opinion.lower_bound} + "
                f"{right_op.opinion.lower_bound}) / 2 = {median.lower_bound:.2f}"
            )
            print(
                f"  ω (peak) = ({left_op.opinion.peak} + "
                f"{right_op.opinion.peak}) / 2 = {median.peak:.2f}"
            )
            print(
                f"  σ (upper) = ({left_op.opinion.upper_bound} + "
                f"{right_op.opinion.upper_bound}) / 2 = {median.upper_bound:.2f}"
            )
    elif m % 2 == 1:
        if not is_likert:
            print(f"  ρ (lower) = {median.lower_bound:.2f} (from middle expert)")
            print(f"  ω (peak) = {median.peak:.2f} (from middle expert)")
            print(f"  σ (upper) = {median.upper_bound:.2f} (from middle expert)")

    median_centroid = median.centroid
    if is_likert:
        print(f"\nMedian centroid: {median_centroid:.2f}")
    else:
        display_centroid(median, "Median centroid")

    return median, median_centroid


def display_step_3_best_compromise(
    mean: FuzzyTriangleNumber, median: FuzzyTriangleNumber
) -> tuple[FuzzyTriangleNumber, float]:
    """
    Display STEP 3: Best Compromise calculation.

    Args:
        mean: Arithmetic mean fuzzy number
        median: Median fuzzy number

    Returns:
        Tuple of (best_compromise, best_compromise_centroid)
    """
    print_section("STEP 3: Best Compromise (ΓΩMean)")

    print("\nFormula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2")

    # Use the average method
    from src.models.fuzzy_number import FuzzyTriangleNumber

    best_compromise = FuzzyTriangleNumber.average([mean, median])

    print(
        f"\nπ (lower) = ({mean.lower_bound:.2f} + {median.lower_bound:.2f}) / 2 = "
        f"{best_compromise.lower_bound:.2f}"
    )
    print(f"φ (peak) = ({mean.peak:.2f} + {median.peak:.2f}) / 2 = {best_compromise.peak:.2f}")
    print(
        f"ξ (upper) = ({mean.upper_bound:.2f} + {median.upper_bound:.2f}) / 2 = "
        f"{best_compromise.upper_bound:.2f}"
    )

    best_compromise_centroid = best_compromise.centroid
    print(
        f"\nBest Compromise: ΓΩMean({best_compromise.lower_bound:.2f}, "
        f"{best_compromise.peak:.2f}, {best_compromise.upper_bound:.2f})"
    )
    print(
        f"Best compromise centroid: "
        f"({best_compromise.lower_bound:.2f} + {best_compromise.peak:.2f} + "
        f"{best_compromise.upper_bound:.2f}) / 3 = {best_compromise_centroid:.2f}"
    )

    return best_compromise, best_compromise_centroid


def display_step_4_max_error(mean_centroid: float, median_centroid: float) -> float:
    """
    Display STEP 4: Maximum Error calculation.

    Args:
        mean_centroid: Centroid of arithmetic mean
        median_centroid: Centroid of median

    Returns:
        Maximum error value
    """
    print_section("STEP 4: Maximum Error (Δmax)")

    print("\nFormula: Δmax = |centroid(Γ) - centroid(Ω)| / 2")
    print("This is the precision indicator (lower is better)")

    max_error = abs(mean_centroid - median_centroid) / 2

    print(f"\nMean centroid (Gx): {mean_centroid:.2f}")
    print(f"Median centroid (Gx): {median_centroid:.2f}")
    print(f"Δmax = |{mean_centroid:.2f} - {median_centroid:.2f}| / 2 = {max_error:.2f}")

    return max_error


def calculate_agreement_level(
    max_error: float, thresholds: tuple[float, float] = (1.0, 3.0)
) -> str:
    """
    Determine expert agreement level based on max error.

    Args:
        max_error: Maximum error value
        thresholds: Tuple of (good_threshold, moderate_threshold)

    Returns:
        Agreement level: "good", "moderate", or "low"
    """
    good_threshold, moderate_threshold = thresholds
    if max_error < good_threshold:
        return "good"
    elif max_error < moderate_threshold:
        return "moderate"
    else:
        return "low"
