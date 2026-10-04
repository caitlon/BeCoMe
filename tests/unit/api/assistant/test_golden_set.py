"""Unit tests for the shape of the committed retrieval golden set (no network)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from api.assistant.rag.corpus import SNIPPET_INCLUDE, build_manifest

ROOT = Path(__file__).resolve().parents[4]
GOLDEN_SET = ROOT / "scripts" / "assistant" / "golden_set.jsonl"

_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_JSON_PATH_SEPARATOR = " > "


def _rows() -> list[dict[str, Any]]:
    """Read the golden set into plain dicts, one per non-blank line."""
    return [
        json.loads(line)
        for line in GOLDEN_SET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _markdown_headings(path: Path) -> set[str]:
    """Collect a markdown file's heading texts, following a snippet include.

    A docs/dev page is only a `--8<--` include of a README that lives next to the
    code, and the assistant indexes the page's resolved text, so the headings a golden
    entry can name are the target's.

    :param path: The markdown file.
    :return: Heading texts without their leading hashes, code fences skipped.
    """
    text = path.read_text(encoding="utf-8")
    match = SNIPPET_INCLUDE.search(text)
    if match:
        text = (ROOT / match.group(1)).read_text(encoding="utf-8")
    headings = set()
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (heading := _MARKDOWN_HEADING.match(line)):
            headings.add(heading.group(1))
    return headings


def _json_section_exists(path: Path, section: str) -> bool:
    """Report whether an i18n JSON file has an object at the key path a section names.

    :param path: The i18n JSON file.
    :param section: Key path joined by " > ", the form the loader gives a section.
    :return: True when every key on the path exists and the last one is an object.
    """
    node: Any = json.loads(path.read_text(encoding="utf-8"))
    for key in section.split(_JSON_PATH_SEPARATOR):
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return isinstance(node, dict)


class TestGoldenSetShape:
    """The golden set stays large enough, bilingual and anchored in public documents."""

    def test_it_holds_at_least_thirty_records(self):
        """
        GIVEN the committed golden set
        WHEN its records are counted
        THEN there are at least thirty
        """
        assert len(_rows()) >= 30

    def test_it_has_at_least_twelve_records_in_each_language(self):
        """
        GIVEN the committed golden set
        WHEN its records are counted by language
        THEN English and Czech each have at least twelve, and no other language appears
        """
        languages = [row["lang"] for row in _rows()]

        assert set(languages) == {"en", "cs"}
        assert languages.count("en") >= 12
        assert languages.count("cs") >= 12

    def test_ids_are_unique(self):
        """
        GIVEN the committed golden set
        WHEN its ids are collected
        THEN none repeats
        """
        ids = [row["id"] for row in _rows()]

        assert len(ids) == len(set(ids))

    def test_every_record_has_a_question_gold_sources_and_facts(self):
        """
        GIVEN the committed golden set
        WHEN each record is read
        THEN it carries a question, a category, at least one gold source and at least one fact
        """
        for row in _rows():
            assert row["question"].strip(), row["id"]
            assert row["category"].strip(), row["id"]
            assert row["gold_sources"], row["id"]
            assert row["expected_facts"], row["id"]
            assert all(fact.strip() for fact in row["expected_facts"]), row["id"]

    def test_no_fact_calls_the_confidence_label_high_agreement(self):
        """
        GIVEN the committed golden set
        WHEN the expected facts are searched for the retired wording
        THEN none says "high agreement": the label is High Confidence, and it does not
             say whether the experts agreed
        """
        for row in _rows():
            for fact in row["expected_facts"]:
                assert "high agreement" not in fact.lower(), row["id"]

    def test_every_gold_path_is_a_public_corpus_source(self):
        """
        GIVEN the public layer of the corpus manifest
        WHEN each gold source's path is looked up in it
        THEN it is there, so the repository's public golden set names no private document
        """
        public_paths = {
            source.path.relative_to(ROOT).as_posix()
            for source in build_manifest(repo_root=ROOT, private_dirs=[])
        }

        for row in _rows():
            for source in row["gold_sources"]:
                assert source["path"] in public_paths, (row["id"], source["path"])

    @pytest.mark.parametrize("row", _rows(), ids=lambda row: row["id"])
    def test_every_gold_section_exists_in_its_file(self, row):
        """
        GIVEN a golden-set record
        WHEN each gold source's section is looked up in its file
        THEN a markdown heading with that text, or a JSON object at that key path, is there
        """
        for source in row["gold_sources"]:
            path = ROOT / source["path"]
            if path.suffix == ".json":
                assert _json_section_exists(path, source["section"]), source
            else:
                assert source["section"] in _markdown_headings(path), source
