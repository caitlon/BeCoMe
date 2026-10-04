"""Unit tests for the answer grader (invented answers, no model and no database)."""

import importlib.util
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[4]


def _load():
    """Import the script by path, since `scripts/` is not a package.

    :return: The imported `grade_answers` module.
    """
    spec = importlib.util.spec_from_file_location(
        "grade_answers", ROOT / "scripts" / "assistant" / "grade_answers.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["grade_answers"] = module
    spec.loader.exec_module(module)
    return module


ga = _load()

ENGLISH_ANSWERS = [
    "The best compromise is 30.68.",
    "Yes. The project has 22 experts and the results are ready.",
    "To invite an expert, open the project, choose Experts and send the invitation by email.",
    "The median is the middle value of the sorted peaks, which is why it is less sensitive to "
    "extreme opinions than the mean.",
    "I could not find this in the documentation, so I cannot say what the limit is.",
    "BeCoMe stands for Best Compromise Mean. It is a method for aggregating expert opinions "
    "given as triangular fuzzy numbers, and it is what this application computes.",
    "- The mean is 36.36\n- The median is 25.0\n- The maximum error is 5.68",
    "What the result shows is the best compromise, the arithmetic mean and the median of the "
    "peaks, together with the maximum error that the experts disagree by.",
    "There are two ways to export the data, and both are available from the project page.",
    'The tool labels this value "nejlepsi kompromis" in Czech, and the number it shows is the '
    "same as the best compromise in the English interface.",
    'The Czech name is "nejlepší kompromis", which is the best compromise of the group, and '
    "it is shown with the maximum error.",
]
CZECH_ANSWERS = [
    "Nejlepší kompromis je 30,68.",
    "Ano, projekt má 22 expertů a výsledky jsou připravené.",
    "Experta pozvete tak, že otevřete projekt, zvolíte Experti a odešlete pozvánku e-mailem.",
    "Medián je prostřední hodnota seřazených vrcholů, a proto je méně citlivý na extrémní "
    "názory než průměr.",
    "V dokumentaci jsem to nenašel, takže nemohu říct, jaký je limit.",
    "BeCoMe znamená Best Compromise Mean. Je to metoda pro agregaci názorů expertů zadaných "
    "jako trojúhelníková fuzzy čísla a právě ji tato aplikace počítá.",
    "- Průměr je 36,36\n- Medián je 25,0\n- Maximální chyba je 5,68",
    "Výsledek ukazuje best compromise, aritmetický průměr a medián vrcholů a také maximální "
    "chybu, o kterou se experti rozcházejí.",
    "Data lze exportovat dvěma způsoby a oba jsou dostupné na stránce projektu.",
    "Výsledek s hodnocením High Confidence znamená, že se experti shodují a že chyba je malá.",
]
QUOTED_ENGLISH_IN_CZECH = [
    'Hodnotu nazýváme "best compromise" a je to průměr, který aplikace počítá z názorů.',
    "Pole High Confidence se zobrazí, když je maximální chyba malá.",
]


def _row(answer: str | None = "The best compromise is 30.68. [1]", **overrides: Any) -> dict:
    """A recorded answer row with only the fields the grader reads."""
    row: dict[str, Any] = {
        "id": "q1",
        "arm": "a",
        "status": "ok",
        "answer": answer,
        "sources": [{"n": 1, "layer": "public"}, {"n": 2, "layer": "local"}],
        "tool_calls": [],
        "checks": {"citations_valid": True, "numbers_grounded": True, "ungrounded_numbers": []},
        "latency_s": 2.0,
    }
    row.update(overrides)
    return row


class TestDetectLanguage:
    """The detector counts function words and diacritic words per language."""

    @pytest.mark.parametrize("text", ENGLISH_ANSWERS)
    def test_english_answers_are_english(self, text):
        # GIVEN an assistant-style English answer, WHEN detected, THEN en
        assert ga.detect_language(text) == "en"

    @pytest.mark.parametrize("text", CZECH_ANSWERS + QUOTED_ENGLISH_IN_CZECH)
    def test_czech_answers_are_czech(self, text):
        # GIVEN an assistant-style Czech answer, WHEN detected, THEN cs
        assert ga.detect_language(text) == "cs"

    @pytest.mark.parametrize("text", ["", "30.68", "36,36 25,0", "Yes", "Ano.", "[1]"])
    def test_numbers_and_very_short_answers_are_unknown(self, text):
        # GIVEN a text with no evidence of a language, WHEN detected, THEN unknown
        assert ga.detect_language(text) == "unknown"

    @pytest.mark.parametrize(
        "text", ["I've no idea.", "We've found nothing.", "It\u2019s not here."]
    )
    def test_an_apostrophe_keeps_a_contraction_one_word(self, text):
        # GIVEN English with I've, We've or it's, whose "ve" or "s" is a Czech word alone
        # WHEN detected, THEN it is English, not Czech
        assert ga.detect_language(text) == "en"

    @pytest.mark.parametrize("text", ["Ano, 22.", "Ne, to nelze.", "Vysledek: 30,68"])
    def test_terse_czech_without_evidence_is_unknown(self, text):
        # GIVEN terse Czech answers that hold no diacritic and no listed function word
        # WHEN detected, THEN the language is not guessed
        assert ga.detect_language(text) == "unknown"

    def test_tie_is_unknown(self):
        # GIVEN one Czech diacritic word and one English function word
        # WHEN detected, THEN the language is not guessed
        assert ga.detect_language("Nejlepší the") == "unknown"


class TestReadCitations:
    """Numeric references are split from pseudo citations."""

    def test_numbers_are_counted_once_and_checked_against_sources(self):
        # GIVEN citations [1], [1, 3] and the range [2-3] with sources 1 and 2
        used, labels = ga.read_citations("A [1]. B [1, 3]. C [2-3].", {1, 2})
        # THEN three numbers are used, two of them real
        assert used == {"used": [1, 2, 3], "valid": 2}
        assert labels == []

    @pytest.mark.parametrize(
        ("answer", "label"),
        [
            ("Data [project_data].", "project_data"),
            ("See [Source 1].", "Source 1"),
            ("Viz [Zdroj 2].", "Zdroj 2"),
            ("Docs [docs].", "docs"),
            ("Docs [doc1].", "doc1"),
            ("Docs [Docs].", "Docs"),
            ("Data [data 3].", "data 3"),
            ("Viz [Projekt 2].", "Projekt 2"),
            ("Tool [tool].", "tool"),
        ],
    )
    def test_labels_are_pseudo_citations(self, answer, label):
        # GIVEN a bracketed label that is not a source number
        used, labels = ga.read_citations(answer, {1})
        # THEN it is a pseudo citation and no source is cited
        assert labels == [label]
        assert used == {"used": [], "valid": 0}

    @pytest.mark.parametrize(
        "answer",
        ["[TODO]", "[BeCoMe]", "[Q1-Q3]", "[i.e.]", "[v1.2]", "[sic]", "[see above]"],
    )
    def test_other_brackets_are_ordinary_text(self, answer):
        # GIVEN a bracket that is not a source label
        # WHEN read, THEN it is neither a citation nor a pseudo citation
        assert ga.read_citations(f"Text {answer} more.", {1}) == ({"used": [], "valid": 0}, [])

    def test_links_numbering_decimals_and_checkboxes_are_not_citations(self):
        # GIVEN a markdown link, list numbering, a fuzzy number, words and a checkbox
        answer = "1. Read [docs](http://x.invalid/a).\n2. Peaks [11.54, 14.19] [lower 6]. [x]"
        # WHEN read, THEN nothing counts
        assert ga.read_citations(answer, {1}) == ({"used": [], "valid": 0}, [])

    def test_a_numbered_link_is_a_citation_as_the_product_reads_it(self):
        # GIVEN [1](url), WHEN read, THEN it cites source 1
        assert ga.read_citations("See [1](http://x.invalid).", {1})[0] == {
            "used": [1],
            "valid": 1,
        }

    def test_labels_keep_order_and_are_listed_once(self):
        # GIVEN repeated pseudo citations in mixed order
        _, labels = ga.read_citations("[docs] a [Source 1] b [docs] c [project_data]", set())
        # THEN each appears once, in order of appearance
        assert labels == ["docs", "Source 1", "project_data"]


class TestExpectedNumbers:
    """The pendlers numbers are matched in the forms the rules allow."""

    @pytest.mark.parametrize(
        "answer",
        [
            "The best compromise is 30.68.",
            "Nejlepší kompromis je 30,68.",
            "It is about 30.7 points.",
            "It is about 30.6 points.",
            "It is 30.68% of the range.",
            "The result, 30.68 km, is given.",
            "1. Result: 30.68",
        ],
    )
    def test_best_compromise_forms_count(self, answer):
        # GIVEN an answer that states 30.68 in an allowed form
        # WHEN counted, THEN the expected value is found
        assert ga.count_expected_numbers(answer, [30.68]) == 1

    @pytest.mark.parametrize(
        "answer",
        ["It is about 31.", "It is 30.", "The error is 15.68.", "It is 130.68.", "No numbers."],
    )
    def test_other_forms_do_not_count(self, answer):
        # GIVEN an integer rounding, a truncation to an integer or a longer number
        # WHEN counted, THEN the expected value is not found
        assert ga.count_expected_numbers(answer, [30.68]) == 0

    def test_a_number_inside_another_number_does_not_count(self):
        # GIVEN 5.68 only as part of 15.68, WHEN counted, THEN it is not stated
        assert ga.count_expected_numbers("The error is 15.68.", [5.68]) == 0
        assert ga.count_expected_numbers("The error is 15.68 and 5.68.", [5.68]) == 1

    def test_integer_valued_expected_counts_as_integer_and_decimals(self):
        # GIVEN the median 25.0, WHEN the answer says 25, 25.0 or 25,0, THEN it counts
        for answer in ("The median is 25.", "The median is 25.0.", "Medián je 25,0."):
            assert ga.count_expected_numbers(answer, [25.0]) == 1

    def test_one_decimal_integer_needs_its_decimal(self):
        # GIVEN 25.04, whose one-decimal rounding is 25.0
        # WHEN the answer says 25.0, THEN it counts; a bare 25 does not
        assert ga.count_expected_numbers("It is 25.0.", [25.04]) == 1
        assert ga.count_expected_numbers("It is 25.", [25.04]) == 0

    def test_several_expected_numbers_are_counted_separately(self):
        # GIVEN the pendlers values and an answer with two of the four
        answer = "Mean 36.36, median 25.0, 22 experts."
        # WHEN counted, THEN two are found
        assert ga.count_expected_numbers(answer, [30.68, 36.36, 25.0, 5.68]) == 2

    def test_citation_indices_are_not_numbers(self):
        # GIVEN an expected 5.0 and an answer that cites [5]
        assert ga.count_expected_numbers("Described in [5].", [5.0]) == 0


class TestHasMarkdown:
    """Bold, italic, headings and list markers count."""

    @pytest.mark.parametrize(
        "text",
        ["A **bold** word", "An *italic* word", "# Title\ntext", "- one\n- two", "1. one\n2. two"],
    )
    def test_markers_are_found(self, text):
        assert ga.has_markdown(text) is True

    @pytest.mark.parametrize(
        "text", ["Plain text.", "It costs 2 * 3 and 4 * 5.", "The value is 30.68."]
    )
    def test_plain_text_is_not_markdown(self, text):
        assert ga.has_markdown(text) is False


class TestGradeRow:
    """One row is graded against its question."""

    def test_failed_row_has_null_grades_and_does_not_raise(self):
        # GIVEN a turn that did not end ok, WHEN graded
        row = _row(answer=None, status="http_500", sources=None, checks=None, tool_calls=None)
        question = {"id": "q1", "lang": "en", "expected_numbers": [1.0], "block": "b"}
        grade = ga.grade_row(row, question)
        # THEN it is not completed, every check is null and the block is still carried
        assert grade["completed"] is False
        assert grade["status"] == "http_500"
        assert grade["latency_s"] == 2.0
        assert grade["block"] == "b"
        assert grade["answer_lang"] is None
        assert grade["citations"] is None
        assert grade["pseudo_citations"] is None
        assert grade["numbers_recall"] is None
        assert grade["has_markdown"] is None

    def test_ok_row_gets_every_check(self):
        # GIVEN an English answer with a citation, a pseudo citation and a number
        question = {
            "id": "q1",
            "lang": "en",
            "expected_numbers": [30.68, 5.68],
            "block": "results",
            "style": "terse",
        }
        grade = ga.grade_row(_row("The best compromise is 30.68. [1] [docs]"), question)
        # THEN the grade carries the checks
        assert grade["completed"] is True
        assert grade["answer_lang"] == "en"
        assert grade["lang_match"] is True
        assert grade["citations"] == {"used": [1], "valid": 1}
        assert grade["pseudo_citations"] == ["docs"]
        assert (grade["expected_numbers_found"], grade["expected_numbers_total"]) == (1, 2)
        assert grade["numbers_recall"] == 0.5
        assert grade["local_source_share"] == 0.5
        assert grade["has_markdown"] is False
        assert (grade["block"], grade["style"]) == ("results", "terse")

    def test_language_match_is_null_when_the_language_is_unknown(self):
        # GIVEN a terse Czech answer to a Czech question
        grade = ga.grade_row(_row("Ano, 22."), {"id": "q1", "lang": "cs"})
        # THEN the language is unknown and so is the match
        assert grade["answer_lang"] == "unknown"
        assert grade["lang_match"] is None

    def test_language_mismatch(self):
        # GIVEN a Czech question answered in English
        grade = ga.grade_row(_row("The best compromise is 30.68."), {"id": "q1", "lang": "cs"})
        # THEN the languages do not match
        assert grade["lang_match"] is False

    def test_ungrounded_numbers_come_from_the_row_unchanged(self):
        # GIVEN a row whose product check flagged 99
        row = _row(checks={"ungrounded_numbers": ["99"]})
        # WHEN graded, THEN the flag is copied, not recomputed
        assert ga.grade_row(row, {"id": "q1"})["ungrounded_numbers"] == ["99"]

    def test_unanswerable_question_records_whether_a_number_was_stated(self):
        # GIVEN unanswerable questions, one answered with a number and one without
        question = {"id": "q1", "answerable": False}
        with_number = ga.grade_row(_row("The limit is 250 experts."), question)
        without = ga.grade_row(_row("1. I cannot find that. [1]"), question)
        # THEN only the first stated a number; an answerable question leaves it null
        assert with_number["stated_any_number"] is True
        assert without["stated_any_number"] is False
        assert ga.grade_row(_row("It is 250."), {"id": "q1"})["stated_any_number"] is None

    def test_no_sources_gives_null_local_share(self):
        # GIVEN an answer with no sources, WHEN graded, THEN the share is null
        assert ga.grade_row(_row(sources=[]), {"id": "q1"})["local_source_share"] is None

    @pytest.mark.parametrize("mode", ["hybrid", "agent"])
    def test_opinions_tool_is_true_or_false_in_a_mode_with_tools(self, mode):
        # GIVEN a question that needs opinions and rows of a mode that has tools
        question = {"id": "q1", "needs_opinions": True}
        called = ga.grade_row(_row(mode=mode, tool_calls=["get_project_opinions"]), question)
        missed = ga.grade_row(_row(mode=mode, tool_calls=["get_project"]), question)
        empty = ga.grade_row(_row(mode=mode, tool_calls=[]), question)
        # THEN it is called, not called, and an empty list means not called
        assert called["called_opinions_tool"] is True
        assert missed["called_opinions_tool"] is False
        assert empty["called_opinions_tool"] is False

    def test_opinions_tool_is_null_in_workflow_mode_whatever_tool_calls_holds(self):
        # GIVEN workflow rows, which have no tools, with an empty or a stray list
        question = {"id": "q1", "needs_opinions": True}
        for tool_calls in ([], ["get_project_opinions"]):
            grade = ga.grade_row(_row(mode="workflow", tool_calls=tool_calls), question)
            # THEN it is neither a call nor a failure to call
            assert grade["called_opinions_tool"] is None

    def test_opinions_tool_is_null_when_the_question_does_not_need_it(self):
        # GIVEN a question without needs_opinions, WHEN graded, THEN the check is null
        grade = ga.grade_row(_row(mode="agent", tool_calls=[]), {"id": "q1"})
        assert grade["called_opinions_tool"] is None


class TestSummarizeArm:
    """The per-arm summary averages the checks that apply."""

    def test_summary_values(self):
        # GIVEN three rows: two completed and one failed
        questions = {
            "q1": {"id": "q1", "lang": "cs", "expected_numbers": [30.68], "needs_opinions": True},
            "q2": {"id": "q2", "lang": "en", "answerable": False},
            "q3": {"id": "q3", "lang": "cs"},
        }
        grades = [
            ga.grade_row(
                _row(
                    "Nejlepší kompromis je 30,68. [docs]",
                    mode="agent",
                    tool_calls=["get_project_opinions"],
                ),
                questions["q1"],
            ),
            ga.grade_row(_row("**No** data. It is 7.", id="q2", latency_s=4.0), questions["q2"]),
            ga.grade_row(_row(None, id="q3", status="Timeout", sources=None), questions["q3"]),
        ]
        # WHEN summarized
        summary = ga.summarize_arm(grades, questions)
        # THEN each figure is over the rows it applies to
        assert summary["n"] == 3
        assert summary["completed_share"] == pytest.approx(2 / 3)
        assert summary["lang_match_share"] == 1.0
        assert summary["lang_match_share_cs"] == 1.0
        assert summary["lang_unknown"] == 0
        assert summary["pseudo_citation_share"] == 0.5
        assert summary["numbers_recall_mean"] == 1.0
        assert summary["unanswerable_stated_number_share"] == 1.0
        assert summary["local_source_share_mean"] == 0.5
        assert summary["opinions_tool_share"] == 1.0
        assert summary["markdown_share"] == 0.5
        assert summary["median_latency_s"] == 3.0
        assert summary["missing"] == 0

    def test_language_shares_leave_out_rows_of_unknown_language(self):
        # GIVEN a decided match, a mismatch and a terse answer, all to Czech questions
        questions = {q: {"id": q, "lang": "cs"} for q in ("q1", "q2", "q3")}
        grades = [
            ga.grade_row(_row("Nejlepší kompromis je 30,68."), questions["q1"]),
            ga.grade_row(_row("The best compromise is 30.68.", id="q2"), questions["q2"]),
            ga.grade_row(_row("Ano, 22.", id="q3"), questions["q3"]),
        ]
        # WHEN summarized, THEN the terse row is counted apart and out of both shares
        summary = ga.summarize_arm(grades, questions)
        assert summary["lang_unknown"] == 1
        assert summary["lang_match_share"] == 0.5
        assert summary["lang_match_share_cs"] == 0.5

    def test_missing_counts_questions_with_no_row(self):
        # GIVEN three questions and rows for only one of them
        questions = {q: {"id": q} for q in ("q1", "q2", "q3")}
        grades = [ga.grade_row(_row(), questions["q1"])]
        # WHEN summarized, THEN the other two are missing and completed_share is still 1.0
        summary = ga.summarize_arm(grades, questions)
        assert summary["missing"] == 2
        assert summary["completed_share"] == 1.0

    def test_empty_denominators_are_null(self):
        # GIVEN only a failed row, WHEN summarized, THEN the checks are null
        questions = {"q1": {"id": "q1"}}
        grades = [ga.grade_row(_row(None, status="Timeout"), questions["q1"])]
        summary = ga.summarize_arm(grades, questions)
        assert summary["completed_share"] == 0.0
        assert summary["lang_match_share"] is None
        assert summary["lang_match_share_cs"] is None
        assert summary["pseudo_citation_share"] is None
        assert summary["numbers_recall_mean"] is None
        assert summary["local_source_share_mean"] is None
        assert summary["markdown_share"] is None
        assert summary["median_latency_s"] is None
        assert summary["lang_unknown"] == 0


def _files(tmp_path, rows, questions):
    """Write an answers file and a questions file.

    :param tmp_path: The test's temporary directory.
    :param rows: Row dicts, or None for no answers file.
    :param questions: Question records, or raw lines when they are strings.
    :return: ``(answers, questions)`` paths.
    """
    answers, questions_path = tmp_path / "answers.jsonl", tmp_path / "questions.jsonl"
    if rows is not None:
        answers.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    lines = [q if isinstance(q, str) else json.dumps(q) for q in questions]
    questions_path.write_text("\n".join(lines), encoding="utf-8")
    return answers, questions_path


def _main(answers, questions, output, *extra):
    """Run the grader's command line on the given paths."""
    return ga.main(
        ["--answers", str(answers), "--questions", str(questions), "--output", str(output), *extra]
    )


class TestMean:
    """The mean helper of the summary."""

    def test_empty_list_has_no_mean(self):
        # GIVEN nothing to average, THEN the mean is null, not 0.0
        assert ga._mean([]) is None

    def test_mean_of_values(self):
        assert ga._mean([1.0, 2.0, 6.0]) == 3.0


# Thirty invented differences whose resample means keep the ranks around 500 and 9500 apart.
DIFFS = [
    0.65, 1.25, 1.24, 1.6, -0.14, 1.9, 0.7, 1.24, 1.26, 1.79, -0.18, 0.1, 1.15, 0.76, 1.25,
    0.09, 1.87, -0.97, 1.17, 0.12, -0.92, 1.03, -0.85, -0.3, -0.03, -0.53, -0.51, -0.78, 1.54,
    -0.75,
]  # fmt: skip


def _resample_means(n_resamples):
    """Sort the means of the seeded resampling the bootstrap is defined by.

    :param n_resamples: How many resamples to draw.
    :return: ``(sorted resample means, the differences)`` for seed 11.
    """
    rng = random.Random(11)
    means = [statistics.fmean(rng.choices(DIFFS, k=len(DIFFS))) for _ in range(n_resamples)]
    return sorted(means), DIFFS


class TestPairedBootstrap:
    """The paired bootstrap is deterministic and keeps pairs together."""

    def test_identical_inputs_give_zero(self):
        # GIVEN two equal samples, THEN the difference and its interval are zero
        assert ga.paired_bootstrap([1.0, 0.0, 1.0], [1.0, 0.0, 1.0], seed=1) == (0, 0, 0)

    def test_constant_shift_is_the_shift_everywhere(self):
        # GIVEN a constant shift of 0.5
        a = [1.5, 2.5, 0.5, 3.5]
        b = [1.0, 2.0, 0.0, 3.0]
        # THEN the mean and both bounds equal it
        assert ga.paired_bootstrap(a, b, seed=7) == pytest.approx((0.5, 0.5, 0.5))

    def test_same_seed_same_result_other_seed_may_differ(self):
        # GIVEN noisy paired scores
        a = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
        b = [0, 0, 1, 0, 0, 1, 1, 0, 0, 1]
        first = ga.paired_bootstrap(a, b, seed=3, n_resamples=500)
        # THEN a repeat with the seed is identical and the interval holds the mean
        assert ga.paired_bootstrap(a, b, seed=3, n_resamples=500) == first
        mean, low, high = first
        assert low <= mean <= high
        assert low < high

    def test_two_pairs_give_the_whole_range_at_ninety_percent(self):
        # GIVEN differences 0 and 1: a resample mean is 0, 0.5 or 1, each end held by a
        # quarter of the resamples, so the 5th and 95th percentiles are the extremes
        assert ga.paired_bootstrap([0.0, 1.0], [0.0, 0.0], seed=5) == (0.5, 0.0, 1.0)

    @pytest.mark.parametrize(
        ("n_resamples", "level", "low_rank", "high_rank"),
        [(10000, 0.90, 500, 9500), (20, 0.5, 5, 15), (7, 0.99, 0, 6)],
    )
    def test_the_interval_is_read_at_exact_ranks(self, n_resamples, level, low_rank, high_rank):
        # GIVEN the sorted means of the same seeded resampling
        means, diffs = _resample_means(n_resamples)
        # WHEN the bootstrap runs with that seed
        mean, low, high = ga.paired_bootstrap(
            diffs, [0.0] * len(diffs), n_resamples=n_resamples, seed=11, level=level
        )
        # THEN the bounds are the elements at the stated ranks, so a shifted index fails
        assert (low, high) == (means[low_rank], means[high_rank])
        assert mean == statistics.fmean(diffs)

    def test_the_data_tells_neighbouring_ranks_apart(self):
        # GIVEN the 10000 resample means of the rank test
        means, _ = _resample_means(10000)
        # THEN ranks 499 to 501 and 9499 to 9501 are all different, so that test would
        # notice a bound read one rank off, as a float rounding of the percentile would
        assert means[499] < means[500] < means[501]
        assert means[9499] < means[9500] < means[9501]

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError, match="differ in length"):
            ga.paired_bootstrap([1.0, 2.0], [1.0], seed=1)

    def test_empty_inputs_and_bad_level_raise(self):
        with pytest.raises(ValueError, match="empty"):
            ga.paired_bootstrap([], [], seed=1)

    @pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5])
    def test_a_level_outside_zero_and_one_raises(self, level):
        with pytest.raises(ValueError, match="level"):
            ga.paired_bootstrap([1.0], [0.0], seed=1, level=level)

    @pytest.mark.parametrize("n_resamples", [0, -3])
    def test_fewer_than_one_resample_raises(self, n_resamples):
        with pytest.raises(ValueError, match="n_resamples"):
            ga.paired_bootstrap([1.0], [0.0], seed=1, n_resamples=n_resamples)


class TestMain:
    """The command line joins rows to questions and writes grades and a summary."""

    def test_grades_the_latest_row_per_question_and_arm(self, tmp_path, capsys):
        # GIVEN a failed row retried to ok, a row of another arm and a row with no question
        rows = [
            _row(None, status="Timeout", sources=None),
            _row("The best compromise is 30.68. [1]"),
            _row("Nejlepší kompromis je 30,68.", arm="b"),
            _row("Stray.", id="unknown"),
        ]
        record = {
            "id": "q1",
            "lang": "en",
            "question": "What is the Zephyr marker?",
            "expected_numbers": [30.68],
        }
        answers, questions = _files(tmp_path, rows, [record])
        output, summary = tmp_path / "grades.jsonl", tmp_path / "out" / "summary.json"
        # WHEN graded, with a summary in a directory that does not exist yet
        code = _main(answers, questions, output, "--summary", str(summary))
        # THEN the retried row wins, the stray row is skipped and nothing prints an answer
        assert code == 0
        grades = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
        assert [(g["arm"], g["completed"], g["numbers_recall"]) for g in grades] == [
            ("a", True, 1.0),
            ("b", True, 1.0),
        ]
        assert set(json.loads(summary.read_text(encoding="utf-8"))) == {"a", "b"}
        captured = capsys.readouterr()
        assert "skipped 1 rows" in captured.err
        shown = captured.out + captured.err
        assert "Zephyr" not in shown
        assert not any(str(row["answer"]) in shown for row in rows if row["answer"])

    def test_a_missing_questions_file_exits_two(self, tmp_path, capsys):
        # GIVEN a questions file that is missing
        answers, _ = _files(tmp_path, [_row()], [])
        # WHEN graded, THEN the exit code is 2 with a message
        assert _main(answers, tmp_path / "missing.jsonl", tmp_path / "out.jsonl") == 2
        assert "cannot read the inputs" in capsys.readouterr().err

    @pytest.mark.parametrize("rows", [None, []])
    def test_a_missing_or_empty_answers_file_leaves_the_outputs_alone(self, tmp_path, rows):
        # GIVEN existing grades and summary, and answers that are missing or empty
        answers, questions = _files(tmp_path, rows, [{"id": "q1"}])
        output, summary = tmp_path / "grades.jsonl", tmp_path / "summary.json"
        output.write_text("kept grades", encoding="utf-8")
        summary.write_text("kept summary", encoding="utf-8")
        # WHEN graded, THEN the run fails and neither file is touched
        assert _main(answers, questions, output, "--summary", str(summary)) == 2
        assert output.read_text(encoding="utf-8") == "kept grades"
        assert summary.read_text(encoding="utf-8") == "kept summary"

    def test_no_row_for_a_known_question_exits_two_without_writing(self, tmp_path, capsys):
        # GIVEN rows whose ids are not in the questions file
        answers, questions = _files(tmp_path, [_row(id="other")], [{"id": "q1"}])
        output = tmp_path / "grades.jsonl"
        # WHEN graded, THEN the run fails and the output is not created
        assert _main(answers, questions, output) == 2
        assert not output.exists()
        assert "no answer row" in capsys.readouterr().err

    @pytest.mark.parametrize("target", ["answers", "questions"])
    @pytest.mark.parametrize("flag", ["--output", "--summary"])
    def test_an_output_that_is_an_input_is_refused(self, tmp_path, capsys, target, flag):
        # GIVEN an output flag that points at one of the inputs
        answers, questions = _files(tmp_path, [_row()], [{"id": "q1"}])
        path = {"answers": answers, "questions": questions}[target]
        before = path.read_text(encoding="utf-8")
        other = tmp_path / "other.json"
        args = [str(path), str(other)] if flag == "--output" else [str(other), str(path)]
        # WHEN graded, THEN the exit code is 2 and the input is intact
        code = _main(answers, questions, args[0], "--summary", args[1])
        assert code == 2
        assert path.read_text(encoding="utf-8") == before
        assert "must not be an input" in capsys.readouterr().err

    def test_output_and_summary_must_differ(self, tmp_path):
        # GIVEN one path for both outputs
        answers, questions = _files(tmp_path, [_row()], [{"id": "q1"}])
        same = tmp_path / "same.json"
        # WHEN graded, THEN the run is refused
        assert _main(answers, questions, same, "--summary", str(same)) == 2

    @pytest.mark.parametrize(
        "bad",
        ["[1, 2]", '{"lang": "en"}', "not json", '"text"'],
    )
    def test_a_bad_question_record_exits_two(self, tmp_path, capsys, bad):
        # GIVEN a questions file with a record that is not an object with an id
        answers, questions = _files(tmp_path, [_row()], [{"id": "q1"}, bad])
        # WHEN graded, THEN the exit code is 2 and the message names the line
        assert _main(answers, questions, tmp_path / "grades.jsonl") == 2
        assert "question record 2" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("expected_numbers", [None]),
            ("expected_numbers", ["30,68"]),
            ("expected_numbers", 30.68),
            ("expected_numbers", None),
            ("expected_numbers", [True]),
            ("expected_numbers", [float("nan")]),
            ("answerable", "no"),
            ("needs_opinions", 1),
            ("lang", ["cs"]),
            ("block", 3),
            ("project", 7),
        ],
    )
    def test_a_question_field_of_the_wrong_type_exits_two(self, tmp_path, capsys, field, value):
        # GIVEN a record whose field has the wrong type, on the second line
        bad = json.dumps({"id": "q2", field: value})
        answers, questions = _files(tmp_path, [_row()], [{"id": "q1"}, bad])
        # WHEN graded, THEN the exit code is 2 and the message names the line and the field
        assert _main(answers, questions, tmp_path / "grades.jsonl") == 2
        message = capsys.readouterr().err
        assert f"question record 2: {field}" in message

    def test_well_typed_optional_fields_are_accepted(self, tmp_path):
        # GIVEN every optional field with its type, and nulls for the absent ones
        record = {
            "id": "q1",
            "lang": "cs",
            "block": "b",
            "style": None,
            "project": None,
            "answerable": True,
            "needs_opinions": False,
            "expected_numbers": [30.68, 25, 5.0],
        }
        answers, questions = _files(tmp_path, [_row()], [record])
        # WHEN graded, THEN it runs
        assert _main(answers, questions, tmp_path / "grades.jsonl") == 0

    def test_a_repeated_question_id_exits_two(self, tmp_path, capsys):
        # GIVEN two question records with the same id
        answers, questions = _files(tmp_path, [_row()], [{"id": "q1"}, {"id": "q1"}])
        # WHEN graded, THEN the exit code is 2 and the message names the line
        assert _main(answers, questions, tmp_path / "grades.jsonl") == 2
        assert "question record 2 repeats an id" in capsys.readouterr().err
