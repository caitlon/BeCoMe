"""Regression tests for the case-study numbers shown on the frontend.

frontend/src/data/caseStudies.ts stores its bestCompromise/maxError results as
static, hand-maintained numbers -- nothing recalculates them at runtime. This
module parses that TypeScript file as text, rebuilds each case's expert
opinions, runs them through the real BeCoMeCalculator, and asserts the stored
numbers match what the calculator actually produces from the same opinions.
A mismatch means the displayed numbers no longer reflect the BeCoMe method
and caseStudies.ts must be corrected.

useLocalizedCaseStudies() overwrites result.interpretation with a translated
string from frontend/src/i18n/locales/{en,cs}/caseStudies.json at runtime, so
this module also checks that free-text prose for the same numbers: the value
actually shown to a user can drift from the real calculation even while
result.bestCompromise/maxError in caseStudies.ts stays correct.

Test coverage is driven by whatever cases caseStudies.ts actually contains,
parsed at collection time, rather than a hardcoded id list -- a new case
study is covered automatically instead of silently going untested.
"""

import json
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
EN_CASE_STUDIES_JSON = (
    Path(__file__).parent.parent.parent
    / "frontend"
    / "src"
    / "i18n"
    / "locales"
    / "en"
    / "caseStudies.json"
)
CS_CASE_STUDIES_JSON = (
    Path(__file__).parent.parent.parent
    / "frontend"
    / "src"
    / "i18n"
    / "locales"
    / "cs"
    / "caseStudies.json"
)

_NUMBER = r"-?\d+(?:\.\d+)?"

_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CASE_ID_RE = re.compile(r'id:\s*"(?P<id>\w+)"')
_EXPERTS_FIELD_RE = re.compile(r"experts:\s*(?P<experts>\d+)")
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
    :ivar experts_field: The case's declared ``experts: N`` count, as shown to users
    :ivar stored_best_compromise: ``result.bestCompromise`` as written in caseStudies.ts
    :ivar stored_max_error: ``result.maxError`` as written in caseStudies.ts
    """

    case_id: str
    opinions: list[ExpertOpinion]
    experts_field: int
    stored_best_compromise: float
    stored_max_error: float


def _strip_js_comments(source: str) -> str:
    """
    Strip '//' line comments and '/* ... */' block comments from TypeScript source.

    Applied before any other regex in this module runs, so a stale, commented-out
    result or opinion literal cannot shadow the live one: re.search() always
    returns the first match, and without this pass a commented-out block placed
    before the real one would win.

    This is a plain regex strip, not a tokenizer: it has no notion of string
    literals, so a "//" or "/*" inside a quoted string would be misread as a
    comment start. None of the case-study fields this module parses (id,
    experts, dataType, opinions, result) contain such sequences, so the
    limitation is safe here but would not generalize to arbitrary TypeScript
    source.

    :param source: Raw TypeScript source text
    :return: Source text with comments removed
    """
    without_block_comments = _BLOCK_COMMENT_RE.sub("", source)
    return _LINE_COMMENT_RE.sub("", without_block_comments)


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
    experts/dataType/opinions/result fields regardless of how the surrounding
    object literal is formatted.

    :param source: Full contents of caseStudies.ts, with comments already stripped
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


def _parse_experts_field(block: str, case_id: str) -> int:
    """
    Parse the declared 'experts: N' field from a single case block.

    This is the expert count shown to users next to the case study (e.g. "22
    experts") and is independent of how many opinions the regex parser
    actually found -- comparing the two catches both a parser regression and
    a displayed count that fell out of sync with the opinions array.

    :param block: Raw source slice for one case, as returned by _split_case_blocks
    :param case_id: Case id, used only to build the error message
    :return: The declared expert count
    :raises ValueError: If the 'experts' field cannot be located in the block
    """
    match = _EXPERTS_FIELD_RE.search(block)
    if match is None:
        raise ValueError(f"Could not locate 'experts: N' field for case '{case_id}'")
    return int(match.group("experts"))


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
    :raises ValueError: If a case block is missing its experts, dataType,
        opinions, or result fields
    """
    source = _strip_js_comments(_read_case_studies_source())
    blocks = _split_case_blocks(source)

    parsed: dict[str, ParsedCaseStudy] = {}
    for case_id, block in blocks.items():
        data_type_match = _DATA_TYPE_RE.search(block)
        if data_type_match is None:
            raise ValueError(f"Could not locate 'dataType' for case '{case_id}'")
        data_type = data_type_match.group("data_type")

        opinions = _parse_opinions(block, data_type)
        experts_field = _parse_experts_field(block, case_id)
        stored_best_compromise, stored_max_error = _parse_stored_result(block)

        parsed[case_id] = ParsedCaseStudy(
            case_id=case_id,
            opinions=opinions,
            experts_field=experts_field,
            stored_best_compromise=stored_best_compromise,
            stored_max_error=stored_max_error,
        )
    return parsed


def _load_interpretation_prose(path: Path) -> dict[str, str]:
    """
    Load the per-case 'interpretation' prose from a caseStudies.json locale file.

    useLocalizedCaseStudies() overwrites result.interpretation with this
    translated string at runtime, so this free text -- not caseStudies.ts -- is
    what actually reaches the user for that field.

    :param path: Path to a locale's caseStudies.json (e.g. locales/en/caseStudies.json)
    :return: Mapping of case id to its 'interpretation' string
    :raises FileNotFoundError: If the locale file is missing
    """
    if not path.exists():
        raise FileNotFoundError(f"Case-study translation file not found: {path}")
    data: dict[str, dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))
    return {
        case_id: case_data["interpretation"]
        for case_id, case_data in data.items()
        if "interpretation" in case_data
    }


def _format_en(value: float) -> str:
    """
    Format a rounded number the way English case-study prose writes it.

    :param value: Already-rounded number (2 decimal places)
    :return: Fixed-point string with a dot decimal separator, e.g. "56.74"
    """
    return f"{value:.2f}"


def _format_cs(value: float) -> str:
    """
    Format a rounded number the way Czech case-study prose writes it.

    :param value: Already-rounded number (2 decimal places)
    :return: Fixed-point string with a comma decimal separator, e.g. "56,74"
    """
    return f"{value:.2f}".replace(".", ",")


@pytest.fixture(scope="module")
def parsed_case_studies() -> dict[str, ParsedCaseStudy]:
    """
    Parse frontend/src/data/caseStudies.ts once per module.

    :return: Mapping of case id to its ParsedCaseStudy
    """
    return _load_parsed_case_studies()


@pytest.fixture(scope="module")
def en_interpretations() -> dict[str, str]:
    """
    Load the English 'interpretation' prose for every case study.

    :return: Mapping of case id to its English interpretation string
    """
    return _load_interpretation_prose(EN_CASE_STUDIES_JSON)


@pytest.fixture(scope="module")
def cs_interpretations() -> dict[str, str]:
    """
    Load the Czech 'interpretation' prose for every case study.

    :return: Mapping of case id to its Czech interpretation string
    """
    return _load_interpretation_prose(CS_CASE_STUDIES_JSON)


# Parsed once at collection time so @pytest.mark.parametrize below covers
# whatever cases caseStudies.ts actually contains, instead of a hardcoded id
# list that a new case study could silently slip past. A parse failure here
# surfaces as a collection error, which is at least as loud as a test failure.
_CASE_IDS = sorted(_load_parsed_case_studies())

_EXPECTED_CASE_IDS = frozenset({"budget", "floods", "pendlers"})


class TestStripJsComments:
    """Unit tests for the comment-stripping pass that runs before any regex parsing.

    A commented-out 'result' or opinion literal must not be able to shadow the
    live one, because re.search() always returns the first match in the source.
    """

    def test_removes_line_comment(self) -> None:
        """A trailing '//' comment is removed but the surrounding code stays."""
        # GIVEN
        source = "const x = 1; // trailing note\nconst y = 2;"

        # WHEN
        stripped = _strip_js_comments(source)

        # THEN
        assert "trailing note" not in stripped
        assert "const x = 1;" in stripped
        assert "const y = 2;" in stripped

    def test_removes_block_comment_spanning_multiple_lines(self) -> None:
        """A '/* ... */' block comment is removed even when it spans line breaks."""
        # GIVEN
        source = "const x = 1;\n/* stale\nblock */\nconst y = 2;"

        # WHEN
        stripped = _strip_js_comments(source)

        # THEN
        assert "stale" not in stripped
        assert "const x = 1;" in stripped
        assert "const y = 2;" in stripped

    def test_commented_out_result_does_not_shadow_live_result(self) -> None:
        """A stale result literal commented out ahead of the live one must lose."""
        # GIVEN: the stale block textually precedes the live one, so an
        # unstripped source would let re.search() match it first
        source = (
            'id: "budget"\n'
            '// result: { bestCompromise: 999, maxError: 999, interpretation: "stale" },\n'
            'result: { bestCompromise: 56.74, maxError: 0.76, interpretation: "live" },\n'
        )

        # WHEN
        best_compromise, max_error = _parse_stored_result(_strip_js_comments(source))

        # THEN
        assert best_compromise == 56.74
        assert max_error == 0.76


class TestFrontendCaseStudyNumbers:
    """Regression tests: caseStudies.ts numbers must match the real BeCoMe calculation."""

    def test_parser_discovers_expected_case_ids(
        self, parsed_case_studies: dict[str, ParsedCaseStudy]
    ) -> None:
        """A parser regression that finds zero (or too few) cases must fail loudly."""
        # THEN
        found = set(parsed_case_studies)
        assert found >= _EXPECTED_CASE_IDS, (
            f"Expected to find case ids {sorted(_EXPECTED_CASE_IDS)} in caseStudies.ts, "
            f"but the parser only found {sorted(found)} -- check the regex parser"
        )

    @pytest.mark.parametrize("case_id", _CASE_IDS)
    def test_stored_result_matches_calculator(
        self,
        calculator: BeCoMeCalculator,
        parsed_case_studies: dict[str, ParsedCaseStudy],
        case_id: str,
    ) -> None:
        """Stored result.bestCompromise/maxError must equal BeCoMeCalculator's output."""
        # GIVEN
        case = parsed_case_studies[case_id]

        # GUARD: a parser regression, or a stale displayed expert count, must fail loudly
        assert len(case.opinions) == case.experts_field, (
            f"{case_id}: parsed {len(case.opinions)} expert opinions from caseStudies.ts, "
            f"but its 'experts:' field declares {case.experts_field} -- either the regex "
            f"parser under- or over-matched, or the displayed expert count is stale"
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

    @pytest.mark.parametrize("case_id", _CASE_IDS)
    def test_interpretation_prose_matches_calculator(
        self,
        calculator: BeCoMeCalculator,
        parsed_case_studies: dict[str, ParsedCaseStudy],
        en_interpretations: dict[str, str],
        cs_interpretations: dict[str, str],
        case_id: str,
    ) -> None:
        """The localized interpretation prose must quote the calculator's own numbers.

        useLocalizedCaseStudies() overwrites result.interpretation with the
        translated string from caseStudies.json at runtime, so that free text,
        not result.bestCompromise/maxError, is what the user actually reads.
        test_stored_result_matches_calculator does not cover this: caseStudies.ts
        can stay correct while the prose drifts, since nothing else ties the two
        together.
        """
        # GIVEN
        case = parsed_case_studies[case_id]
        result = calculator.calculate_compromise(case.opinions)
        best_compromise = round(result.best_compromise.centroid, 2)
        max_error = round(result.max_error, 2)

        # WHEN/THEN: english prose, dot decimal separator
        en_interpretation = en_interpretations[case_id]
        expected_en_best_compromise = _format_en(best_compromise)
        expected_en_max_error = _format_en(max_error)
        assert expected_en_best_compromise in en_interpretation, (
            f"{case_id} (en): expected bestCompromise '{expected_en_best_compromise}' "
            f"in the interpretation prose, but it was not found. "
            f"interpretation={en_interpretation!r}"
        )
        assert expected_en_max_error in en_interpretation, (
            f"{case_id} (en): expected maxError '{expected_en_max_error}' "
            f"in the interpretation prose, but it was not found. "
            f"interpretation={en_interpretation!r}"
        )

        # WHEN/THEN: czech prose, comma decimal separator
        cs_interpretation = cs_interpretations[case_id]
        expected_cs_best_compromise = _format_cs(best_compromise)
        expected_cs_max_error = _format_cs(max_error)
        assert expected_cs_best_compromise in cs_interpretation, (
            f"{case_id} (cs): expected bestCompromise '{expected_cs_best_compromise}' "
            f"in the interpretation prose, but it was not found. "
            f"interpretation={cs_interpretation!r}"
        )
        assert expected_cs_max_error in cs_interpretation, (
            f"{case_id} (cs): expected maxError '{expected_cs_max_error}' "
            f"in the interpretation prose, but it was not found. "
            f"interpretation={cs_interpretation!r}"
        )
