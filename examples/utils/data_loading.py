"""Data loading utilities for BeCoMe examples."""

from pathlib import Path

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

_METADATA_PREFIXES = ("CASE:", "DESCRIPTION:", "EXPERTS:")


def _parse_metadata_line(line: str, metadata: dict[str, str]) -> bool:
    """
    Try to parse a metadata line (CASE/DESCRIPTION/EXPERTS prefix).

    :param line: Stripped input line
    :param metadata: Dictionary to update in-place
    :return: True if the line was a metadata line, False otherwise
    """
    for prefix in _METADATA_PREFIXES:
        if line.startswith(prefix):
            key = prefix.rstrip(":").lower()
            if key == "experts":
                key = "num_experts"
            metadata[key] = line.split(prefix, maxsplit=1)[1].strip()
            return True
    return False


def _parse_expert_line(line: str) -> ExpertOpinion:
    """
    Parse a pipe-delimited expert opinion line.

    :param line: Line in format ``ExpertID | Lower | Peak | Upper``
    :return: Parsed ExpertOpinion
    :raises ValueError: If format is invalid or values are not numeric
    """
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

    fuzzy_number = FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)
    return ExpertOpinion(expert_id=expert_id, opinion=fuzzy_number)


def load_data_from_txt(filepath: str) -> tuple[list[ExpertOpinion], dict[str, str]]:
    """
    Load expert opinions from text file.

    Expected file format::

        CASE: CaseName
        DESCRIPTION: Case description
        EXPERTS: N

        # Format: ExpertID | Lower | Peak | Upper
        Expert1 | 10 | 15 | 20
        Expert2 | 12 | 18 | 25

    :param filepath: Path to the text file containing expert opinions
    :return: Tuple of (expert opinions list, metadata dict with 'case',
             'description', 'num_experts')
    :raises FileNotFoundError: If the file doesn't exist
    :raises ValueError: If the file format is invalid
    """
    file_path = Path(filepath)

    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")

    metadata: dict[str, str] = {}
    opinions: list[ExpertOpinion] = []

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if _parse_metadata_line(line, metadata):
                continue

            if "|" in line:
                opinions.append(_parse_expert_line(line))

    if "num_experts" in metadata:
        expected_count: int = int(metadata["num_experts"])
        actual_count: int = len(opinions)
        if actual_count != expected_count:
            raise ValueError(f"Expected {expected_count} experts but loaded {actual_count}")

    return opinions, metadata
