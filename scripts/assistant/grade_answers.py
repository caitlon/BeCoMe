#!/usr/bin/env python3
"""Answer grader: deterministic checks over the answers the eval runner recorded.

Reads the rows of ``eval_answers.py`` (the latest row per question and arm), joins each to
its question by ``id`` and writes one grade per row. No model is called and no setting is
read. Every check is a function of the answer text and the row's own fields, so a rerun
gives the same grades.

Per row: the answer's language and whether it matches the question's, the numeric
citations used and how many name a real source, the bracketed labels that are not source
numbers, how many of the question's expected numbers the answer states, the numbers the
product's grounding check flagged, whether an unanswerable question got a number anyway,
the share of local sources, whether the expert-opinions tool was called, and whether the
answer uses markdown. A row whose turn failed has ``completed: false`` and null grades.

The summary per arm is printed and, with ``--summary``, written as JSON. The numbers and
citations are read with the product's own parser (``api.assistant.agent.checks``), so the
grader and the grounding check cannot disagree about what a number is. Logs and prints
carry counts only, never an answer or a question.

    uv run python scripts/assistant/grade_answers.py --answers answers.jsonl \\
        --questions questions.jsonl --output grades.jsonl --summary summary.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from api.assistant.agent.checks import _citation_spans, _places, _scan_numbers, _strip_answer
from api.assistant.agent.tools import get_project_opinions

OPINIONS_TOOL = get_project_opinions.name
#: The modes whose agent can call tools. ``workflow`` has none: the service prefetches the data.
TOOL_MODES = frozenset(["hybrid", "agent"])
#: What an optional question field must be when present (null counts as absent).
_FIELD_TYPES: dict[str, type] = {
    "lang": str,
    "block": str,
    "style": str,
    "project": str,
    "answerable": bool,
    "needs_opinions": bool,
}

#: Letters that exist in Czech and not in English (lowercase; the text is lowercased first).
CZECH_DIACRITICS = frozenset("áčďéěíňóřšťúůýž")
#: Czech function words. Words that are also English words (so, to, pro, ten) and the one
#: letter prepositions are left out: they would count for the wrong language.
_CZECH_FUNCTION_WORDS_TEXT = (
    "je jsou jsem jste jsme byl byla bylo byly bude budou se si že na ve ze ke "
    "při před než nebo ale který která které kteří "
    "jak co proč kde kdy jeho její jejich není nejsou má mají "
    "také ještě již jen tedy tak pokud protože podle mezi "
    "tím této tohoto tento tato toto tyto"
)
CZECH_FUNCTION_WORDS = frozenset(_CZECH_FUNCTION_WORDS_TEXT.split())
#: English function words. Unlike the product's list for questions, "is" and "it" are in:
#: here the words are counted against the Czech ones, so one acronym cannot decide.
_ENGLISH_FUNCTION_WORDS_TEXT = (
    "the what how does which are is it why when where can should of and with for if this "
    "that from was were did there will would could has have not than these those your our "
    "their in as an or at be you its into"
)
ENGLISH_FUNCTION_WORDS = frozenset(_ENGLISH_FUNCTION_WORDS_TEXT.split())
#: The part after the apostrophe of an English contraction or possessive ("I've", "it's").
ENGLISH_CONTRACTION_SUFFIXES = frozenset(["s", "t", "re", "ve", "ll", "d", "m"])
# Fewer words than this carry no evidence of a language.
MIN_WORDS = 2

# A word; an apostrophe inside it keeps it one token, so "I've" never leaves a Czech "ve".
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*")
# A bracket with only digits and separators holds source numbers.
_NUMBERS_ONLY = re.compile(r"[\d\s,;\u2013-]+")
#: The first words of a pseudo citation label: "[Source 1]", "[docs]", "[doc1]".
PSEUDO_LABEL_WORDS = (
    "sources",
    "source",
    "zdroje",
    "zdroj",
    "docs",
    "doc",
    "document",
    "dokument",
    "project",
    "projekt",
    "data",
    "tool",
    "citation",
)
# A bracket label: one of those words with an optional number, or an identifier with an
# underscore ("project_data"). Any other bracket is ordinary text. The lookahead keeps out
# the text of a markdown link, "[docs](http://...)".
_BRACKET_LABEL = re.compile(
    rf"\[((?:{'|'.join(PSEUDO_LABEL_WORDS)})[ ]?\d{{0,3}}|[^\W\d_]\w*_\w+)\](?!\()",
    re.IGNORECASE,
)


def _is_english(word: str) -> bool:
    """Tell whether a word counts for English: a function word or a contraction.

    :param word: A lowercase word as :data:`_WORD` finds it.
    :return: True for a listed function word, or a word like ``i've`` or ``it's``.
    """
    return word in ENGLISH_FUNCTION_WORDS or (
        "'" in word and word.rpartition("'")[2] in ENGLISH_CONTRACTION_SUFFIXES
    )


_BOLD_OR_ITALIC = re.compile(
    r"\*\*[^*\n]+\*\*|__[^_\n]+__|(?<![*\w])\*(?!\s)[^*\n]+?(?<!\s)\*(?![*\w])"
)
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+\S", re.MULTILINE)
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\S", re.MULTILINE)
_ONE_DECIMAL = Decimal("0.1")


def detect_language(text: str) -> str:
    """Say whether an answer is written in English or Czech.

    Each word counts for Czech when it is a Czech function word or holds a Czech diacritic
    letter, and for English when it is an English function word or a contraction such as
    ``I've`` (an apostrophe keeps a word whole). The language with more
    words wins, so an English answer that quotes a Czech phrase stays English and a Czech
    answer that quotes English terms stays Czech.

    :param text: The answer text.
    :return: ``en`` or ``cs``; ``unknown`` for a text of fewer than two words, one with no
        function word and no diacritic (a bare number), or one where the two are tied.
    """
    normalized = unicodedata.normalize("NFC", text).replace("\u2019", "'")
    words = _WORD.findall(normalized.lower())
    if len(words) < MIN_WORDS:
        return "unknown"
    czech = sum(
        word in CZECH_FUNCTION_WORDS or any(char in CZECH_DIACRITICS for char in word)
        for word in words
    )
    english = sum(_is_english(word) for word in words)
    if czech == english:
        return "unknown"
    return "cs" if czech > english else "en"


def read_citations(answer: str, source_numbers: set[int]) -> tuple[dict[str, Any], list[str]]:
    """Split the bracketed references of an answer into source numbers and pseudo citations.

    A bracket of digits and separators (``[1]``, ``[1, 2]``, ``[1-3]``) names source
    numbers, read as the product reads them. Any other bracket the product reads as a
    citation (``[Source 1]``, ``[Zdroj 2]``, ``[doc1]``) is a pseudo citation, and so is an
    identifier with an underscore (``[project_data]``) or a label that starts with one of
    :data:`PSEUDO_LABEL_WORDS`, with an optional number (``[docs]``). Every other bracket
    (``[TODO]``, ``[BeCoMe]``, ``[Q1-Q3]``, ``[i.e.]``), the text of a markdown link and list
    numbering are ordinary text.

    :param answer: The answer text.
    :param source_numbers: The ``n`` of every source the row records.
    :return: ``({"used": sorted numbers, "valid": how many of them name a source}, labels)``,
        the labels once each, in order of appearance.
    """
    used: set[int] = set()
    found: list[tuple[int, str]] = []
    for start, end, numbers in _citation_spans(answer):
        content = answer[start + 1 : end - 1]
        if _NUMBERS_ONLY.fullmatch(content):
            used |= numbers
        else:
            found.append((start, content.strip()))
    found.extend((match.start(), match[1]) for match in _BRACKET_LABEL.finditer(answer))
    labels = list(dict.fromkeys(label for _, label in sorted(found)))
    return {"used": sorted(used), "valid": len(used & source_numbers)}, labels


def stated_numbers(answer: str) -> set[Decimal]:
    """Read the numbers an answer states, as the product's grounding check reads them.

    Links, URLs, citations, dates, identifiers such as ``COVID-19``, list numbering and
    ordinals are not numbers. A token that can be read several ways (``30,68`` is 30.68 or
    30 and 68) contributes every reading.

    :param answer: The answer text.
    :return: The values.
    """
    return {
        number
        for token in _scan_numbers(_strip_answer(answer))
        for reading in token.readings
        for number in reading
    }


def count_expected_numbers(answer: str, expected: Sequence[Any]) -> int:
    """Count the expected numbers that an answer states.

    An expected value, written by the API with two decimals, counts as stated when the
    answer holds it as the same number, with a decimal point or a Czech decimal comma, or
    rounded or truncated to one decimal written with one decimal (30.68 as 30.7 or 30.6).
    A value whose decimals are zero (25.0) also counts as the integer 25. A bare integer
    rounding of a non-integer (31 for 30.68) does not count, and a number is read whole, so
    5.68 does not count inside 15.68.

    :param answer: The answer text.
    :param expected: The expected values, numbers or numeric strings.
    :return: How many of them the answer states.
    """
    stated = stated_numbers(answer)
    found = 0
    for item in expected:
        value = Decimal(str(item))
        one_decimal = {
            value.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP),
            value.quantize(_ONE_DECIMAL, rounding=ROUND_DOWN),
        }
        found += any(
            number == value or (_places(number) == 1 and number in one_decimal) for number in stated
        )
    return found


def has_markdown(answer: str) -> bool:
    """Tell whether an answer uses markdown: bold or italic, a heading or a list.

    :param answer: The answer text.
    :return: True when a marker is present.
    """
    return any(pattern.search(answer) for pattern in (_BOLD_OR_ITALIC, _HEADING, _LIST_ITEM))


def grade_row(row: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    """Grade one recorded answer against its question.

    :param row: A row of the runner's output.
    :param question: The question record with the same ``id``.
    :return: The grade: ``id``, ``arm``, ``status``, ``latency_s``, ``usage`` and ``timing``
        (the row's, or null), ``completed`` and each check. A row whose status is not ``ok`` has null checks.
        ``lang_match`` is also null when the question has no ``lang`` or the answer's language
        is ``unknown``; ``numbers_recall`` without expected numbers; ``stated_any_number``
        unless the question has ``answerable: false``; ``called_opinions_tool`` unless the
        question has ``needs_opinions`` and the row's ``mode`` is ``hybrid`` or ``agent``
        (``workflow`` has no tools, whatever ``tool_calls`` holds; there an empty list means
        the tool was not called); ``local_source_share`` without sources. ``block`` and
        ``style`` are copied from the question for later analysis and are not graded.
    """
    grade: dict[str, Any] = {
        "id": row["id"],
        "arm": row["arm"],
        "status": row["status"],
        "latency_s": row.get("latency_s"),
        "usage": row.get("usage"),
        "timing": row.get("timing"),
        "completed": row["status"] == "ok",
        "block": question.get("block"),
        "style": question.get("style"),
    }
    checks = (
        "answer_lang",
        "lang_match",
        "citations",
        "pseudo_citations",
        "expected_numbers_found",
        "expected_numbers_total",
        "numbers_recall",
        "ungrounded_numbers",
        "stated_any_number",
        "local_source_share",
        "called_opinions_tool",
        "has_markdown",
    )
    grade.update(dict.fromkeys(checks))
    if not grade["completed"]:
        return grade
    answer = row["answer"]
    sources = row["sources"] or []
    answer_lang = detect_language(answer)
    grade["answer_lang"] = answer_lang
    if question.get("lang") and answer_lang != "unknown":
        grade["lang_match"] = answer_lang == question["lang"]
    grade["citations"], grade["pseudo_citations"] = read_citations(
        answer, {source["n"] for source in sources}
    )
    expected = question.get("expected_numbers") or []
    if expected:
        found = count_expected_numbers(answer, expected)
        grade.update(
            expected_numbers_found=found,
            expected_numbers_total=len(expected),
            numbers_recall=found / len(expected),
        )
    grade["ungrounded_numbers"] = (row.get("checks") or {}).get("ungrounded_numbers")
    if question.get("answerable") is False:
        grade["stated_any_number"] = bool(_scan_numbers(_strip_answer(answer)))
    if sources:
        grade["local_source_share"] = sum(s["layer"] == "local" for s in sources) / len(sources)
    if question.get("needs_opinions") and row.get("mode") in TOOL_MODES:
        grade["called_opinions_tool"] = OPINIONS_TOOL in row["tool_calls"]
    grade["has_markdown"] = has_markdown(answer)
    return grade


def _share(flags: list[bool]) -> float | None:
    """Return the share of true flags, or None for an empty list.

    :param flags: The flags.
    :return: The share.
    """
    return sum(flags) / len(flags) if flags else None


def _mean(values: list[float]) -> float | None:
    """Return the mean, or None for an empty list.

    :param values: The values.
    :return: The mean.
    """
    return statistics.fmean(values) if values else None


def summarize_arm(
    grades: list[dict[str, Any]], questions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Summarize the grades of one arm.

    Each share and mean is taken over the completed rows the check applies to, the language
    match over the rows whose language was decided; one with none to average is null.

    :param grades: The arm's grades from :func:`grade_row`.
    :param questions: The question records by ``id``.
    :return: ``n``, ``completed_share``, ``lang_match_share``, ``lang_match_share_cs`` (Czech
        questions only), ``lang_unknown`` (completed rows whose language is ``unknown``),
        ``pseudo_citation_share``, ``numbers_recall_mean``,
        ``unanswerable_stated_number_share``, ``local_source_share_mean``,
        ``opinions_tool_share``, ``markdown_share``, ``median_latency_s``,
        ``median_ttft_ms`` (the server's time to first token, over the completed rows whose
        ``timing.ttft_ms`` is not null: a streamed run; null when there are none),
        ``median_input_tokens``, ``median_output_tokens``, ``median_total_tokens`` and
        ``median_llm_calls`` (over the completed rows that carry ``usage``, rows with incomplete
        usage included, so ``usage_incomplete`` says how many of them are partial sums),
        ``usage_rows`` (how many completed rows carried ``usage``, the medians' denominator),
        ``usage_incomplete`` (completed rows whose usage is not complete) and ``missing``
        (questions that have no row in this arm, for instance because the run stopped early).
    """
    done = [grade for grade in grades if grade["completed"]]
    latencies = [g["latency_s"] for g in done if g["latency_s"] is not None]
    usages = [g["usage"] for g in done if g["usage"] is not None]
    ttfts = [g["timing"]["ttft_ms"] for g in done if (g["timing"] or {}).get("ttft_ms") is not None]
    return {
        "n": len(grades),
        "completed_share": _share([grade["completed"] for grade in grades]),
        "lang_match_share": _share([g["lang_match"] for g in done if g["lang_match"] is not None]),
        "lang_match_share_cs": _share(
            [
                g["lang_match"]
                for g in done
                if g["lang_match"] is not None and questions[g["id"]].get("lang") == "cs"
            ]
        ),
        "lang_unknown": sum(g["answer_lang"] == "unknown" for g in done),
        "pseudo_citation_share": _share([bool(g["pseudo_citations"]) for g in done]),
        "numbers_recall_mean": _mean(
            [g["numbers_recall"] for g in done if g["numbers_recall"] is not None]
        ),
        "unanswerable_stated_number_share": _share(
            [g["stated_any_number"] for g in done if g["stated_any_number"] is not None]
        ),
        "local_source_share_mean": _mean(
            [g["local_source_share"] for g in done if g["local_source_share"] is not None]
        ),
        "opinions_tool_share": _share(
            [g["called_opinions_tool"] for g in done if g["called_opinions_tool"] is not None]
        ),
        "markdown_share": _share([g["has_markdown"] for g in done]),
        "median_latency_s": statistics.median(latencies) if latencies else None,
        "median_ttft_ms": statistics.median(ttfts) if ttfts else None,
        **{
            f"median_{key}": statistics.median(u[key] for u in usages) if usages else None
            for key in ("input_tokens", "output_tokens", "total_tokens", "llm_calls")
        },
        "usage_rows": len(usages),
        "usage_incomplete": sum(not u["complete"] for u in usages),
        "missing": len(questions.keys() - {grade["id"] for grade in grades}),
    }


def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 10000,
    seed: int,
    level: float = 0.90,
) -> tuple[float, float, float]:
    """Estimate the mean paired difference of two arms with a percentile bootstrap.

    The question indices are resampled with replacement, so each resample keeps the pairs
    together. The same seed gives the same interval. The interval is read from the sorted
    resample means by exact ranks: the lower bound is the element at index
    ``floor(n_resamples * (1 - level) / 2)`` and the upper bound the one at
    ``floor(n_resamples * (1 + level) / 2)``, or the last if that is past the end, so 10000
    resamples at ``level=0.90`` give the elements 500 and 9500.

    :param a: One score per question for the first arm.
    :param b: The second arm's scores, in the same question order.
    :param n_resamples: How many resamples to draw.
    :param seed: Seed of the random generator.
    :param level: Width of the interval, between 0 and 1 (0.90 is the 5th to 95th percentile).
    :return: ``(mean of a - b, lower bound, upper bound)``.
    :raises ValueError: If the lengths differ, the inputs are empty, ``n_resamples`` is below
        1, or ``level`` is not between 0 and 1.
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples differ in length: {len(a)} and {len(b)}")
    if not a:
        raise ValueError("paired samples are empty")
    if n_resamples < 1:
        raise ValueError("n_resamples must be at least 1")
    if not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    # A seeded generator for a reproducible resample, not for anything secret.
    rng = random.Random(seed)  # noqa: S311
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(n_resamples))
    tail = (1 - Fraction(str(level))) / 2
    low = means[math.floor(tail * n_resamples)]
    high = means[min(n_resamples - 1, math.floor((1 - tail) * n_resamples))]
    return statistics.fmean(diffs), low, high


def _check_fields(record: dict[str, Any], number: int) -> None:
    """Check the types of a question record's optional fields.

    :param record: The decoded record.
    :param number: Its line among the records, for the message.
    :raises ValueError: If ``expected_numbers`` is not a list of finite numbers, or another
        field is not of its type (null counts as absent).
    """
    for field, kind in _FIELD_TYPES.items():
        if record.get(field) is not None and not isinstance(record[field], kind):
            raise ValueError(f"question record {number}: {field} must be a {kind.__name__}")
    if "expected_numbers" in record:
        values = record["expected_numbers"]
        if not isinstance(values, list) or not all(
            isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                f"question record {number}: expected_numbers must be a list of numbers"
            )


def _load_questions(path: Path) -> dict[str, dict[str, Any]]:
    """Read the question records by ``id``.

    :param path: JSONL file; each record has ``id`` and ``lang`` and optionally ``block``,
        ``style``, ``project`` (strings), ``answerable``, ``needs_opinions`` (booleans) and
        ``expected_numbers`` (a list of numbers).
    :return: ``{id: record}``.
    :raises ValueError: If a record is not valid JSON, not an object, has no id, repeats an
        id, or holds a field of the wrong type. The message names the line and the field,
        never the question.
    """
    records: dict[str, dict[str, Any]] = {}
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for number, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"question record {number} is not valid JSON") from None
        if not isinstance(record, dict) or not record.get("id"):
            raise ValueError(f"question record {number} is not an object with an id")
        if record["id"] in records:
            raise ValueError(f"question record {number} repeats an id")
        _check_fields(record, number)
        records[record["id"]] = record
    return records


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments for one grading run.

    :param argv: The arguments, or None for ``sys.argv``.
    :return: The parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", required=True, type=Path, help="Runner output JSONL")
    parser.add_argument("--questions", required=True, type=Path, help="Questions JSONL")
    parser.add_argument("--output", required=True, type=Path, help="Grades JSONL, overwritten")
    parser.add_argument("--summary", type=Path, default=None, help="Per-arm summary JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Grade the answers, write the grades and print one summary line per arm.

    ``--output`` and ``--summary`` are written only after every row is graded, and never
    over an input.

    :param argv: The arguments, or None for ``sys.argv``.
    :return: 0 on success; 2 when an input cannot be read or holds no row of a known
        question, or an output path is an input.
    """
    # Imported here: the runner module builds the application, which needs the settings,
    # and the checks above do not.
    from scripts.assistant.eval_answers import RunRefusedError, latest_rows

    args = _parse_args(argv)
    outputs = [args.output] if args.summary is None else [args.output, args.summary]
    taken = {args.answers.resolve(), args.questions.resolve()}
    if any(path.resolve() in taken for path in outputs) or len(outputs) != len(
        {path.resolve() for path in outputs}
    ):
        print("--output and --summary must not be an input file or each other", file=sys.stderr)
        return 2
    try:
        questions = _load_questions(args.questions)
        if not args.answers.is_file():
            raise OSError("the answers file does not exist")
        answers = latest_rows(args.answers)
    except (ValueError, OSError, RunRefusedError) as exc:
        print(f"cannot read the inputs: {exc}", file=sys.stderr)
        return 2
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped = 0
    for (question_id, arm), row in answers.items():
        if question_id in questions:
            by_arm[arm].append(grade_row(row, questions[question_id]))
        else:
            skipped += 1
    if not by_arm:
        print("no answer row belongs to a question of the questions file", file=sys.stderr)
        return 2
    summary = {arm: summarize_arm(grades, questions) for arm, grades in by_arm.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as sink:
        for grades in by_arm.values():
            sink.writelines(json.dumps(grade, ensure_ascii=False) + "\n" for grade in grades)
    for arm, values in summary.items():
        print(
            f"arm={arm} " + " ".join(f"{k}={'n/a' if v is None else v}" for k, v in values.items())
        )
    if skipped:
        print(f"skipped {skipped} rows whose id is not in the questions", file=sys.stderr)
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
