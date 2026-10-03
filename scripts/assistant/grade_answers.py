#!/usr/bin/env python3
"""Answer grader: deterministic checks over the answers the eval runner recorded.

Reads the rows of ``eval_answers.py`` (the latest row per question and arm), joins each to
its question by ``id`` and writes one grade per row. No model is called and no setting is
read. Every check is a function of the answer text and the row's own fields, so a rerun
gives the same grades.

Per row: the answer's language and whether it matches the question's, the numeric
citations used and how many name a real source, and the bracketed labels that are not
source numbers. A row whose turn failed has ``completed: false`` and null grades.

The summary per arm is printed and, with ``--summary``, written as JSON. Citations are read
with the product's own parser (``api.assistant.agent.checks``), so the grader and the
grounding check cannot disagree about what a citation is. Logs and prints carry counts
only, never an answer or a question.

    uv run python scripts/assistant/grade_answers.py --answers answers.jsonl \\
        --questions questions.jsonl --output grades.jsonl --summary summary.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from api.assistant.agent.checks import _citation_spans

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


def grade_row(row: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    """Grade one recorded answer against its question.

    :param row: A row of the runner's output.
    :param question: The question record with the same ``id``.
    :return: The grade: ``id``, ``arm``, ``status``, ``latency_s``, ``completed`` and each
        check. A row whose status is not ``ok`` has null checks; ``lang_match`` is also null
        when the question has no ``lang`` or the answer's language is ``unknown``.
    """
    grade: dict[str, Any] = {
        "id": row["id"],
        "arm": row["arm"],
        "status": row["status"],
        "latency_s": row.get("latency_s"),
        "completed": row["status"] == "ok",
    }
    checks = (
        "answer_lang",
        "lang_match",
        "citations",
        "pseudo_citations",
    )
    grade.update(dict.fromkeys(checks))
    if not grade["completed"]:
        return grade
    answer = row["answer"]
    answer_lang = detect_language(answer)
    grade["answer_lang"] = answer_lang
    if question.get("lang") and answer_lang != "unknown":
        grade["lang_match"] = answer_lang == question["lang"]
    grade["citations"], grade["pseudo_citations"] = read_citations(
        answer, {source["n"] for source in row["sources"] or []}
    )
    return grade


def _share(flags: list[bool]) -> float | None:
    """Return the share of true flags, or None for an empty list.

    :param flags: The flags.
    :return: The share.
    """
    return sum(flags) / len(flags) if flags else None


def summarize_arm(
    grades: list[dict[str, Any]], questions: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Summarize the grades of one arm.

    Each share is taken over the completed rows the check applies to, the language match
    over the rows whose language was decided; one with none to average is null.

    :param grades: The arm's grades from :func:`grade_row`.
    :param questions: The question records by ``id``.
    :return: ``n``, ``completed_share``, ``lang_match_share``, ``lang_match_share_cs`` (Czech
        questions only), ``lang_unknown`` (completed rows whose language is ``unknown``),
        ``pseudo_citation_share``, ``median_latency_s`` and ``missing`` (questions that have
        no row in this arm, for instance because the run stopped early).
    """
    done = [grade for grade in grades if grade["completed"]]
    latencies = [g["latency_s"] for g in done if g["latency_s"] is not None]
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
        "median_latency_s": statistics.median(latencies) if latencies else None,
        "missing": len(questions.keys() - {grade["id"] for grade in grades}),
    }


def _load_questions(path: Path) -> dict[str, dict[str, Any]]:
    """Read the question records by ``id``.

    :param path: JSONL file; each record has ``id`` and ``lang``.
    :return: ``{id: record}``.
    :raises ValueError: If a record is not valid JSON, not an object, has no id, or repeats
        an id. The message names the line, never the question.
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
