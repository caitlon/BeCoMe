"""Report corpus chunks that look like planted instructions, at ingest time.

A document in the corpus, a third-party PDF in the private layer for example, can carry
text meant for the answer model instead of the reader: the assistant's own tags, a chat
template's role markers, or a sentence that gives the model orders. Chunk text and
metadata reach the model as excerpts for every tenant that asks a question, so one
planted chunk reaches all of them.

This module only reports. The ingest lists what it found and never stops the build or
drops a chunk: the owner reads the list and decides. The check is a short heuristic over
fixed lists, not a filter, and it will miss paraphrases and flag an honest page that
quotes such text.

It reads the chunks as `split` returns them, before enrichment adds a caption or a
heading path to the text. For each chunk it looks at the chunk's own text, its title and
its section (the `heading_path` metadata), after `strip_invisible`, case folding and
whitespace collapse, so a zero-width character, a different case or a line break inside a
phrase does not hide it.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.documents import Document

from api.assistant.agent.prompt import ASSISTANT_TAGS
from api.assistant.invisible import strip_invisible

# The lists below are a short heuristic, not a filter: they catch the obvious forms and
# nothing is removed because of them. Matched on text that is already case folded.

# An assistant tag, opening or closing, with spaces allowed inside the brackets.
_TAG_PATTERN = re.compile(r"<\s*(/?)\s*(" + "|".join(map(re.escape, ASSISTANT_TAGS)) + r")\s*>")

# Role and turn markers of common chat templates, plus the reasoning tags.
_ROLE_MARKERS: tuple[str, ...] = (
    "<|im_start|>",
    "<|im_end|>",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|start_header_id|>",
    "<|end_header_id|>",
    "<|eot_id|>",
    "[inst]",
    "[/inst]",
    "<<sys>>",
    "<start_of_turn>",
    "<end_of_turn>",
    "<think>",
    "</think>",
)

# Phrases that give the model orders, in English and Czech. Whitespace inside a phrase is
# matched flexibly, so the text is collapsed before these run.
_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bignore (?:all |the |any )?(?:previous|prior|above|earlier) instructions\b",
        r"\bdisregard (?:all |the )?(?:previous|prior|above) (?:instructions|rules)\b",
        r"\byou are now\b",
        r"\bnew instructions\b",
        r"\bsystem prompt\b",
        r"\bdo not tell the user\b",
        r"\bignoruj (?:všechny |předchozí |výše uvedené )*pokyny\b",
        r"\bzapomeň na (?:všechny |předchozí )*pokyny\b",
        r"\bnové pokyny\b",
        r"\bsystémový prompt\b",
        r"\bneříkej (?:to )?uživateli\b",
    )
)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class FlaggedChunk:
    """One chunk the screening found suspicious, with where it came from.

    :param layer: "public", "local", or "" when the chunk carries no layer metadata.
    :param source: The chunk's source path, or its title when it has no path, or "".
    :param section: The chunk's heading path, "" when it has none.
    :param reason: What was found, for example "assistant tag <docs>". Never the
        chunk's text.
    """

    layer: str
    source: str
    section: str
    reason: str


def _normalize(text: str) -> str:
    """Make a text comparable: no invisible characters, one case, single spaces.

    :param text: Chunk text, title or section.
    :return: The text with invisible characters removed, case folded and every run of
        whitespace collapsed to one space.
    """
    return _WHITESPACE.sub(" ", strip_invisible(text).casefold()).strip()


def _tag_reason(text: str) -> str | None:
    """Find an assistant tag in a normalized text.

    :param text: Normalized text.
    :return: "assistant tag <name>" or "assistant tag </name>", or None.
    """
    match = _TAG_PATTERN.search(text)
    if match is None:
        return None
    return f"assistant tag <{match.group(1)}{match.group(2)}>"


def _marker_reason(text: str) -> str | None:
    """Find a chat-template role marker in a normalized text.

    :param text: Normalized text.
    :return: "role marker <marker>" for the first marker found, or None.
    """
    for marker in _ROLE_MARKERS:
        if marker in text:
            return f"role marker {marker}"
    return None


def _phrase_reason(text: str) -> str | None:
    """Find an instruction-like phrase in a normalized text.

    :param text: Normalized text.
    :return: "instruction-like phrase: <the matched words>" or None.
    """
    for pattern in _PHRASE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return f"instruction-like phrase: {match.group(0)}"
    return None


def screen_chunks(chunks: Sequence[Document]) -> list[FlaggedChunk]:
    """List the chunks whose text, title or section looks like planted instructions.

    :param chunks: Chunks as `split` returns them, with the loaders' metadata.
    :return: One FlaggedChunk per flagged chunk, in the order of `chunks`, carrying the
        first reason found: an assistant tag before a role marker before a phrase,
        looking at the text, then the title, then the section for each.
    """
    flagged = []
    for chunk in chunks:
        metadata = chunk.metadata
        title = str(metadata.get("title") or "")
        section = str(metadata.get("heading_path") or "")
        fields = [_normalize(field) for field in (chunk.page_content, title, section)]
        reason = next(
            (
                found
                for check in (_tag_reason, _marker_reason, _phrase_reason)
                for field in fields
                if (found := check(field)) is not None
            ),
            None,
        )
        if reason is not None:
            flagged.append(
                FlaggedChunk(
                    layer=str(metadata.get("layer") or ""),
                    source=str(metadata.get("source") or title),
                    section=section,
                    reason=reason,
                )
            )
    return flagged
