"""Per-request context threaded through the agent, and the registry of cited sources."""

import re
import unicodedata
from dataclasses import dataclass

from api.assistant.client import UserApiClient
from api.assistant.rag.retrieval import DocsRetriever, RetrievedChunk
from api.schemas.assistant import SourceRef

# The longest excerpt of a passage a source reference carries, ellipsis included.
SNIPPET_CHARS = 240

_WHITESPACE_RUN = re.compile(r"\s+")


def _excerpt(text: str, limit: int = SNIPPET_CHARS) -> str:
    """Return the first words of a passage as plain text on one line.

    Whitespace runs collapse to one space and control characters are dropped. A text over
    the limit is cut at the last space that leaves room for the ellipsis, or without
    regard to spaces when it has none, so the result never exceeds ``limit`` characters.

    :param text: The passage as indexed.
    :param limit: The most characters the result may have, ellipsis included.
    :return: The tidied text, ending in an ellipsis when it was cut.
    """
    spaced = _WHITESPACE_RUN.sub(" ", text)
    plain = "".join(
        char for char in spaced if char == " " or not unicodedata.category(char).startswith("C")
    ).strip()
    if len(plain) <= limit:
        return plain
    head = plain[: limit - 1]
    cut = head.rfind(" ")
    return (head[:cut] if cut > 0 else head).rstrip() + "\u2026"


class SourceRegistry:
    """Assigns stable ``[n]`` numbers to retrieved chunks, in first-seen order.

    One instance lives for a single chat request. A chunk is identified by its title,
    its section and its own words (``chunk_text``): the same passage surfacing again
    keeps its first number, so the model's citations stay consistent, while the same
    words under another title or section are a different source. The indexed text is
    not part of the key, because a caption written by another model is not the source.
    """

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._chunks: list[RetrievedChunk] = []
        self._numbers: dict[tuple[str, str, str], int] = {}

    def add(self, chunk: RetrievedChunk) -> int:
        """Register a chunk and return its stable 1-based number.

        :param chunk: The retrieved chunk to register.
        :return: The number to show the model and the user as ``[n]``.
        """
        key = (chunk.title, chunk.section, chunk.chunk_text)
        existing = self._numbers.get(key)
        if existing is not None:
            return existing
        self._chunks.append(chunk)
        number = len(self._chunks)
        self._numbers[key] = number
        return number

    def refs(self) -> list[SourceRef]:
        """Return every registered chunk as a response-ready source reference.

        A local-layer source never carries a url: the layer is private, and whatever
        the index holds in that field must not reach a browser.

        :return: One reference per registered chunk, in registration order.
        """
        return [
            SourceRef(
                n=number,
                title=chunk.title,
                section=chunk.section,
                snippet=_excerpt(chunk.chunk_text),
                url=None if chunk.layer == "local" else chunk.url,
                layer=chunk.layer,
            )
            for number, chunk in enumerate(self._chunks, start=1)
        ]

    def numbered(self) -> list[tuple[int, RetrievedChunk]]:
        """Return every registered chunk with the number it was given.

        The chat service uses it to show the model every source found so far in one
        excerpts block, when a turn has to be answered from what was already gathered.

        :return: One ``(number, chunk)`` pair per registered chunk, in registration order.
        """
        return list(enumerate(self._chunks, start=1))

    def texts(self) -> list[str]:
        """Return what the model is shown for each source, for the number check.

        For every registered chunk: its title, its section when there is one, and its
        own words, as separate strings. A year in a title that the model repeats is
        then grounded. The ``[n]`` marker is left out, because its digits must never
        count as grounded numbers, and so is the generated caption.

        :return: The strings, chunk by chunk, in registration order.
        """
        texts: list[str] = []
        for chunk in self._chunks:
            texts.append(chunk.title)
            if chunk.section:
                texts.append(chunk.section)
            texts.append(chunk.chunk_text)
        return texts


@dataclass
class AssistantContext:
    """Per-turn state a tool call needs.

    :ivar client: API client acting as the current user (GET-only).
    :ivar retriever: Documentation retriever for the search tool and any prefetch.
    :ivar sources: Registry assigning ``[n]`` numbers to retrieved chunks.
    :ivar tool_outputs: Every string a tool has produced so far this turn, kept as
        grounding for :func:`~api.assistant.agent.checks.find_ungrounded_numbers`.
    :ivar current_project_id: The project the user is viewing, if any.
    :ivar locale: The UI locale the request carried (``en`` or ``cs``).
    """

    client: UserApiClient
    retriever: DocsRetriever
    sources: SourceRegistry
    tool_outputs: list[str]
    current_project_id: str | None
    locale: str
