"""Data loading utilities for BeCoMe examples."""

from pathlib import Path

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


def load_data_from_txt(filepath: str) -> tuple[list[ExpertOpinion], dict[str, str]]:
    """
    Load expert opinions from text file.

    Expected file format:
        CASE: CaseName
        DESCRIPTION: Case description
        EXPERTS: N

        # Format: ExpertID | Lower | Peak | Upper
        Expert1 | 10 | 15 | 20
        Expert2 | 12 | 18 | 25
        ...

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

            if line.startswith("CASE:"):
                metadata["case"] = line.split("CASE:")[1].strip()
            elif line.startswith("DESCRIPTION:"):
                metadata["description"] = line.split("DESCRIPTION:")[1].strip()
            elif line.startswith("EXPERTS:"):
                metadata["num_experts"] = line.split("EXPERTS:")[1].strip()
            elif "|" in line:
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
                opinion = ExpertOpinion(expert_id=expert_id, opinion=fuzzy_number)
                opinions.append(opinion)

    if "num_experts" in metadata:
        expected_count: int = int(metadata["num_experts"])
        actual_count: int = len(opinions)
        if actual_count != expected_count:
            raise ValueError(f"Expected {expected_count} experts but loaded {actual_count}")

    return opinions, metadata
