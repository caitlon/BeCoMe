"""Factory function for creating reference case dictionaries."""

from pathlib import Path

from examples.utils import load_data_from_txt


def create_case(
    case_name: str,
    expected_result: dict,
    data_filename: str | None = None,
) -> dict:
    """Create a reference case dictionary with opinions and expected results.

    This factory function encapsulates the common logic for loading expert
    opinions from text files and combining them with expected results from
    Excel reference implementation.

    :param case_name: Name of the case (e.g., "Budget", "Floods", "Pendlers")
    :param expected_result: Dictionary with expected calculation results from Excel.
                           Should contain fields like best_compromise_peak,
                           max_error, num_experts, etc.
    :param data_filename: Name of the data file in examples/data/ directory.
                         Defaults to {case_name.lower()}_case.txt if not specified.
    :return: Dictionary with three keys:
             - opinions: List of ExpertOpinion objects loaded from txt file
             - expected_result: Dictionary with expected calculation results
             - description: Case study description from txt file metadata
    :raises FileNotFoundError: If the data file does not exist
    :raises ValueError: If the data file format is invalid

    >>> BUDGET_CASE = create_case(
    ...     case_name="Budget",
    ...     expected_result={
    ...         "best_compromise_peak": 51.25,
    ...         "max_error": 2.20,
    ...         "num_experts": 22,
    ...     },
    ... )
    """
    if data_filename is None:
        data_filename = f"{case_name.lower()}_case.txt"

    data_dir = Path(__file__).parent.parent.parent / "examples" / "data"
    txt_file = data_dir / data_filename
    opinions, metadata = load_data_from_txt(str(txt_file))

    return {
        "opinions": opinions,
        "expected_result": expected_result,
        "description": metadata.get("description", f"{case_name} case study"),
    }
