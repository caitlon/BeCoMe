"""Report corpus chunks that look like planted instructions, at ingest time.

A document in the corpus, a third-party PDF in the private layer for example, can carry
text meant for the answer model instead of the reader: the assistant's own tags, a chat
template's role markers, or a sentence that gives the model orders. Chunk text and
metadata reach the model as excerpts for every tenant that asks a question, so one
planted chunk reaches all of them.

This module only reports and never drops a chunk: the owner reads the list and decides,
and the ingest (``pipeline.build_collection``) acts on it. The check is a short heuristic
over fixed lists, not a filter, and it will miss paraphrases and flag an honest page that
quotes such text.

It reads the chunks as `split` returns them, before enrichment adds a caption or a
heading path to the text. For each chunk it looks at the chunk's own text, its title and
its section (the `heading_path` metadata), after `strip_invisible`, NFKC
normalization, case folding and whitespace collapse, so a zero-width character, a
decomposed letter, a fullwidth bracket, a different case or a line break inside a phrase
does not hide it. The phrase patterns also run on a copy with the diacritics folded away,
so Czech typed without them matches too.
"""

import hashlib
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.documents import Document

from api.assistant.agent.prompt import ASSISTANT_TAGS
from api.utils.invisible import strip_invisible

# The lists below are a short heuristic, not a filter: they catch the obvious forms and
# nothing is removed because of them. Matched on text that is already case folded.

# An assistant tag, opening or closing, with spaces allowed inside the brackets. The answer side
# has its own grammar, on one line only, in ``api/assistant/agent/wrapper_tags.py``.
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

# Phrases that give the model orders, in English and Czech: a short heuristic, not a
# filter. The patterns run on text that is case folded and has its diacritics folded away
# (see `_fold`), so the Czech ones are written without diacritics and also match Czech typed
# without them. Between words they allow any whitespace or none, so a phrase whose spaces
# were replaced by zero-width characters (stripped before these run) still matches; the word
# boundaries at both ends stay.
#
# Left out on purpose, because they flag ordinary how-to text: "from now on" and "od ted",
# "you should answer", "add the text" and "pridejte text", "start every answer with" and
# "close all messages with" and "ukoncete vsechny zpravy", "you must answer" without "always"
# or "never", and an addressee line without a colon or comma after it ("message to the model
# owner"). Also narrowed: "processing the" (only "this" and "these" count, which is what keeps
# "the model processing the opinions" clean), the Czech reader pattern, which has no such guard
# and so leaves out a bare "model", and the Czech "tell the user", "vzdy odpovidej" and "nikdy
# rikej", which need the "ze" ("that") or a colon after them.
_ADDRESSEE = r"(?:(?:ai\s*)?(?:assistant|chatbot|bot|model|llm|language\s*model)|ai)"
_ADDRESSEE_READER = r"(?:assistant|ai|chatbot|bot|model|llm|language\s*model)s?"
_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"\b(?:ignore|disregard)\s*(?:(?:all|the|any|your|my|these|those|every|everything)\s*){0,2}"
        r"(?:(?:previous|prior|above|earlier)\s*)?(?:instructions|rules|prompts?)\b",
        r"\b(?:ignore|disregard)\s*everything\s*above\b",
        r"\bnew\s*instructions\b",
        r"\bsystem\s*prompt\b",
        r"\bdo(?:\s*not|n['\u2019]t)\s*tell\s*the\s*user\b",
        # A note, message or order addressed to the model, then a colon or comma.
        r"\b(?:note|message|instructions?|reminder)\s*(?:for|to)\s*(?:(?:the|any|an|a)\s*)?"
        + _ADDRESSEE
        + r"\s*[:,]",
        r"\b" + _ADDRESSEE_READER + r"\s*(?:reading|processing|summari[sz]ing|parsing)"
        r"\s*(?:this|these)\b",
        # A rule for what to answer when the user asks something.
        r"\bwhen\s*(?:a|the|any)\s*user\s*asks\b.{0,160}?"
        r"\b(?:answer|reply|respond|say|tell\s*them)\s*(?:that|with)\b",
        r"\b(?:add|append|include|insert)\s*the\s*(?:phrase|sentence)\b",
        r"\b(?:end|finish|close)\s*(?:every|each|all|your)\s*"
        r"(?:answers?|responses?|repl(?:y|ies))\s*with\b",
        r"\btell\s*(?:the|every|each|any)\s*users?\s*that\b",
        r"\byou\s*(?:must|have\s*to)\s*(?:always|never)\s*"
        r"(?:answer|reply|respond|say|state|claim|tell)\b",
        r"\bignoruj(?:te)?\s*(?:vsechny\s*|predchozi\s*|vyse\s*uvedene\s*)*(?:pokyny|instrukce)\b",
        r"\bzapomen(?:te)?\s*na\s*(?:vsechny\s*|predchozi\s*)*(?:pokyny|instrukce)\b",
        r"\bnove\s*pokyny\b",
        r"\bsystemovy\s*prompt\b",
        r"\bnerikej(?:te)?\s*(?:to\s*)?uzivateli\b",
        r"\b(?:poznamka|pokyny?|zprava|vzkaz|instrukce)\s*(?:pro\s*)?"
        r"(?:asistent(?:a|ovi)?|ai|umelou\s*inteligenci|model(?:u)?|chatbot(?:a|ovi)?"
        r"|jazykov(?:y|ou)\s*model(?:u)?)\s*[:,]",
        r"\b(?:asistent\w*|ai|chatbot\w*),?\s*(?:ktery|ktera|jenz)\s*"
        r"(?:ctes?|zpracovava(?:s)?|shrnuje(?:s)?)\b",
        r"\bkdyz\s*(?:se\s*)?(?:te\s*)?(?:uzivatel|nekdo)\s*(?:zepta|pta|bude\s*ptat)\b.{0,160}?"
        r"\b(?:odpovez|odpovezte|odpovidej|odpovidejte|rekni|reknete|tvrd|tvrdte)\b",
        r"\b(?:pridej(?:te)?|pripoj(?:te)?|dopln(?:te)?|vloz(?:te)?)\s*(?:na\s*konec\s*)?"
        r"(?:frazi|vetu)\b",
        r"\b(?:ukonci|ukoncete|zakonci|zakoncete|zacni|zacnete|zacinej|zacinejte)\s*"
        r"(?:kazdou|vsechny|svou|svoji)\s*(?:odpoved|odpovedi)\b",
        r"\b(?:rekni|reknete|sdel|sdelte)\s*uzivateli\s*(?:,?\s*ze\b|:)",
        r"\b(?:vzdy|nikdy)\s*(?:odpovidej(?:te)?|odpovez(?:te)?|rikej(?:te)?|tvrd(?:te)?)"
        r"\s*(?:,?\s*ze\b|:)",
    )
)

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class FlaggedChunk:
    """One chunk the screening found suspicious, with where it came from.

    :param layer: "public", "local", or "" when the chunk carries no layer metadata.
    :param source: The chunk's source path, or its title when it has no path, or "".
    :param section: The chunk's heading path, "" when it has none.
    :param reason: What was found, for example "assistant tag <docs>". For a phrase it
        quotes the span matched in the normalized text with its diacritics folded away
        (case folded, whitespace collapsed, every combining mark dropped after NFKD, so carons,
        acutes and rings go and Czech typed without diacritics matches), so it holds words of
        the chunk in that folded form; for a tag or a marker it is a fixed string.
    :param key: `screening_key` of the chunk's text, title and section. Chunks with the
        same text, title and section share a key, so accepting one accepts them all;
        editing any of the three changes it.
    """

    layer: str
    source: str
    section: str
    reason: str
    key: str


def screening_key(text: str, title: str, section: str) -> str:
    """Hash the three fields the screening reads, so an accepted key covers all of them.

    :param text: The chunk's own text, as `split` returns it.
    :param title: The chunk's title metadata, "" when it has none.
    :param section: The chunk's heading path, "" when it has none.
    :return: The sha256 hex digest of the three raw fields joined unambiguously as JSON.
    """
    payload = json.dumps([text, title, section])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    """Make a text comparable: no invisible characters, one case, single spaces.

    :param text: Chunk text, title or section.
    :return: The text with invisible characters removed, compatibility-normalized (NFKC,
        so a decomposed letter or a fullwidth bracket reads as its plain form), case
        folded and every run of whitespace collapsed to one space.
    """
    normalized = unicodedata.normalize("NFKC", strip_invisible(text))
    return _WHITESPACE.sub(" ", normalized.casefold()).strip()


def _fold(text: str) -> str:
    """Drop the diacritics of a normalized text, so Czech typed without them reads the same.

    :param text: Normalized text (see `_normalize`).
    :return: The text decomposed (NFKD) with its combining marks removed.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


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
    :return: "instruction-like phrase: <the matched words>", the words as they read with
        their diacritics folded away, or None.
    """
    folded = _fold(text)
    for pattern in _PHRASE_PATTERNS:
        match = pattern.search(folded)
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
                    key=screening_key(chunk.page_content, title, section),
                )
            )
    return flagged
