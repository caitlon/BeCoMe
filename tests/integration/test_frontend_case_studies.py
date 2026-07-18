"""Regression tests for the case-study numbers shown on the frontend.

frontend/src/data/caseStudies.ts stores its bestCompromise/maxError results as
static, hand-maintained numbers -- nothing recalculates them at runtime. This
module parses that TypeScript file as text, rebuilds each case's expert
opinions, runs them through the real BeCoMeCalculator, and asserts the stored
numbers match what the calculator actually produces from the same opinions.
A mismatch means the displayed numbers no longer reflect the BeCoMe method
and caseStudies.ts must be corrected.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

CASE_STUDIES_TS = (
    Path(__file__).parent.parent.parent / "frontend" / "src" / "data" / "caseStudies.ts"
)

_EXPECTED_EXPERT_COUNTS = {
    "budget": 22,
    "floods": 13,
    "pendlers": 22,
}

_NUMBER = r"-?\d+(?:\.\d+)?"

_CASE_ID_RE = re.compile(r'id:\s*"(?P<id>\w+)"')
_DATA_TYPE_RE = re.compile(r'dataType:\s*"(?P<data_type>interval|likert)"')
_OPINIONS_BLOCK_RE = re.compile(
    r"opinions:\s*\[(?P<body>.*?)\]\s*as\s*(?:ExpertOpinion|LikertOpinion)\[\]",
    re.DOTALL,
)
_INTERVAL_OPINION_RE = re.compile(
    rf"bestProposal:\s*(?P<best_proposal>{_NUMBER}),\s*"
    rf"lowerLimit:\s*(?P<lower_limit>{_NUMBER}),\s*"
    rf"upperLimit:\s*(?P<upper_limit>{_NUMBER})"
)
_LIKERT_OPINION_RE = re.compile(rf'role:\s*"[^"]*",\s*value:\s*(?P<value>{_NUMBER})')
_RESULT_RE = re.compile(
    rf"result:\s*\{{\s*bestCompromise:\s*(?P<best_compromise>{_NUMBER}),\s*"
    rf"maxError:\s*(?P<max_error>{_NUMBER}),"
)


@dataclass(frozen=True)
class ParsedCaseStudy:
    """Case-study data extracted from the frontend TypeScript source.

    :ivar case_id: Case identifier (``budget``, ``floods``, ``pendlers``)
    :ivar opinions: Expert opinions rebuilt from the parsed values
    :ivar stored_best_compromise: ``result.bestCompromise`` as written in caseStudies.ts
    :ivar stored_max_error: ``result.maxError`` as written in caseStudies.ts
    """

    case_id: str
    opinions: list[ExpertOpinion]
    stored_best_compromise: float
    stored_max_error: float


def _read_case_studies_source() -> str:
    """
    Read the frontend case-study data file as raw text.

    :return: Full contents of frontend/src/data/caseStudies.ts
    :raises FileNotFoundError: If the frontend data file is missing
    """
    if not CASE_STUDIES_TS.exists():
        raise FileNotFoundError(f"Frontend case-study data file not found: {CASE_STUDIES_TS}")
    return CASE_STUDIES_TS.read_text(encoding="utf-8")


def _split_case_blocks(source: str) -> dict[str, str]:
    """
    Split the caseStudies.ts source into one raw text slice per case id.

    Each slice starts at a case's ``id: "..."`` literal and runs until the next
    case's id literal (or end of file), so it fully covers that case's
    dataType/opinions/result fields regardless of how the surrounding object
    literal is formatted.

    :param source: Full contents of caseStudies.ts
    :return: Mapping of case id to its raw source slice
    :raises ValueError: If no case id literals are found at all
    """
    matches = list(_CASE_ID_RE.finditer(source))
    if not matches:
        raise ValueError(f"No case study 'id: \"...\"' entries found in {CASE_STUDIES_TS}")

    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        blocks[match.group("id")] = source[start:end]
    return blocks


def _parse_opinions(block: str, data_type: str) -> list[ExpertOpinion]:
    """
    Parse the opinions array of a single case block into ExpertOpinion objects.

    Interval opinions map directly onto a fuzzy triangular number built from
    (lowerLimit, bestProposal, upperLimit). Likert opinions carry a single
    crisp value v, modeled as the degenerate fuzzy number (v, v, v) -- the
    same convention the frontend's BeCoMe write-up uses for Likert scores.

    :param block: Raw source slice for one case, as returned by _split_case_blocks
    :param data_type: Either "interval" or "likert"
    :return: List of ExpertOpinion built from the parsed values, in source order
    :raises ValueError: If the opinions array cannot be located in the block
    """
    opinions_match = _OPINIONS_BLOCK_RE.search(block)
    if opinions_match is None:
        raise ValueError("Could not locate an 'opinions: [...]' array in case block")
    body = opinions_match.group("body")

    opinions: list[ExpertOpinion] = []
    if data_type == "interval":
        for index, match in enumerate(_INTERVAL_OPINION_RE.finditer(body)):
            fuzzy_number = FuzzyTriangleNumber(
                lower_bound=float(match.group("lower_limit")),
                peak=float(match.group("best_proposal")),
                upper_bound=float(match.group("upper_limit")),
            )
            opinions.append(ExpertOpinion(f"expert-{index}", fuzzy_number))
    else:
        for index, match in enumerate(_LIKERT_OPINION_RE.finditer(body)):
            value = float(match.group("value"))
            opinions.append(
                ExpertOpinion(f"expert-{index}", FuzzyTriangleNumber(value, value, value))
            )
    return opinions


def _parse_stored_result(block: str) -> tuple[float, float]:
    """
    Parse the stored bestCompromise/maxError from a single case block.

    :param block: Raw source slice for one case, as returned by _split_case_blocks
    :return: Tuple of (stored bestCompromise, stored maxError) as written in the source
    :raises ValueError: If the result fields cannot be located in the block
    """
    result_match = _RESULT_RE.search(block)
    if result_match is None:
        raise ValueError("Could not locate 'result: { bestCompromise, maxError }' in case block")
    return (
        float(result_match.group("best_compromise")),
        float(result_match.group("max_error")),
    )


def _load_parsed_case_studies() -> dict[str, ParsedCaseStudy]:
    """
    Parse every case study out of the frontend caseStudies.ts source file.

    :return: Mapping of case id to its ParsedCaseStudy
    :raises ValueError: If a case block is missing its dataType, opinions, or result fields
    """
    source = _read_case_studies_source()
    blocks = _split_case_blocks(source)

    parsed: dict[str, ParsedCaseStudy] = {}
    for case_id, block in blocks.items():
        data_type_match = _DATA_TYPE_RE.search(block)
        if data_type_match is None:
            raise ValueError(f"Could not locate 'dataType' for case '{case_id}'")
        data_type = data_type_match.group("data_type")

        opinions = _parse_opinions(block, data_type)
        stored_best_compromise, stored_max_error = _parse_stored_result(block)

        parsed[case_id] = ParsedCaseStudy(
            case_id=case_id,
            opinions=opinions,
            stored_best_compromise=stored_best_compromise,
            stored_max_error=stored_max_error,
        )
    return parsed


@pytest.fixture
def parsed_case_studies() -> dict[str, ParsedCaseStudy]:
    """
    Parse frontend/src/data/caseStudies.ts once per test.

    :return: Mapping of case id to its ParsedCaseStudy
    """
    return _load_parsed_case_studies()


class TestFrontendCaseStudyNumbers:
    """Regression tests: caseStudies.ts numbers must match the real BeCoMe calculation."""

    @pytest.mark.parametrize("case_id,expected_experts", sorted(_EXPECTED_EXPERT_COUNTS.items()))
    def test_stored_result_matches_calculator(
        self,
        calculator: BeCoMeCalculator,
        parsed_case_studies: dict[str, ParsedCaseStudy],
        case_id: str,
        expected_experts: int,
    ) -> None:
        """Stored result.bestCompromise/maxError must equal BeCoMeCalculator's output."""
        # GIVEN
        case = parsed_case_studies[case_id]

        # GUARD: a parser regression must fail loudly, not silently understate the panel
        assert len(case.opinions) == expected_experts, (
            f"{case_id}: parsed {len(case.opinions)} expert opinions from caseStudies.ts, "
            f"expected {expected_experts} -- the regex parser likely under- or over-matched"
        )

        # WHEN
        result = calculator.calculate_compromise(case.opinions)
        computed_best_compromise = round(result.best_compromise.centroid, 2)
        computed_max_error = round(result.max_error, 2)

        # THEN
        assert math.isclose(computed_best_compromise, case.stored_best_compromise, abs_tol=0.005), (
            f"{case_id}: caseStudies.ts stores bestCompromise={case.stored_best_compromise}, "
            f"but BeCoMeCalculator computes {computed_best_compromise} from the same opinions"
        )
        assert math.isclose(computed_max_error, case.stored_max_error, abs_tol=0.005), (
            f"{case_id}: caseStudies.ts stores maxError={case.stored_max_error}, "
            f"but BeCoMeCalculator computes {computed_max_error} from the same opinions"
        )
