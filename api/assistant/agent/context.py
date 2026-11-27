"""Per-request context threaded through the agent, and the registry of cited sources."""

import unicodedata
from dataclasses import dataclass, field

from api.assistant.agent.masking import TurnRoster
from api.assistant.client import UserApiClient
from api.assistant.rag.retrieval import DocsRetriever, RetrievedChunk
from api.schemas.assistant import SourceRef
from api.utils.invisible import strip_invisible

# The longest excerpt of a passage a source reference carries, ellipsis included.
SNIPPET_CHARS = 240


def _excerpt(text: str, limit: int = SNIPPET_CHARS) -> str:
    """Return the first words of a passage as plain text on one line.

    Control characters are dropped first and whitespace runs, including those a dropped
    character leaves behind, then collapse to one space. A text over the limit is cut at
    the last space that leaves room for the ellipsis, or without regard to spaces when it
    has none, so the result never exceeds ``limit`` characters.

    :param text: The passage as indexed.
    :param limit: The most characters the result may have, ellipsis included.
    :return: The tidied text, ending in an ellipsis when it was cut.
    """
    kept = "".join(
        char for char in text if char.isspace() or not unicodedata.category(char).startswith("C")
    )
    plain = " ".join(kept.split())
    if len(plain) <= limit:
        return plain
    cut = plain.rfind(" ", 0, limit)
    head = plain[:cut] if cut > 0 else plain[: limit - 1]
    return head + "\u2026"


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
        the index holds in that field must not reach a browser. It still carries a short
        excerpt of its own words in ``snippet``; only the url is withheld. The title, the
        section and the snippet lose their invisible characters (see
        :func:`~api.utils.invisible.strip_invisible`).

        :return: One reference per registered chunk, in registration order.
        """
        return [
            SourceRef(
                n=number,
                title=strip_invisible(chunk.title),
                section=strip_invisible(chunk.section),
                snippet=_excerpt(strip_invisible(chunk.chunk_text)),
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
    :ivar tool_outputs: Every string a tool has produced so far this turn, which the agent's
        fallback call shows the model again. It does not ground numbers.
    :ivar current_project_id: The project the user is viewing, if any.
    :ivar locale: The UI locale the request carried (``en`` or ``cs``).
    :ivar data_values: The numbers of structured project data (result and opinion values,
        scale bounds, counts, project ids), written as the data blocks write them. They are
        the only project data that
        :func:`~api.assistant.agent.checks.find_ungrounded_numbers` grounds on.
    :ivar text_copies: The free text the model was shown whose digits are part of a repeat of
        it: the names of the projects and of the experts, as the data blocks write them. An
        answer that repeats one verbatim is not checked for the numbers inside it (see the
        ``copies`` argument of ``find_ungrounded_numbers``); they ground nothing.
    :ivar roster: The experts of every opinions list this turn fetched, with their labels.
        The trace of the turn is masked with it.
    :ivar prepared: True once :meth:`~api.assistant.agent.service.AssistantService.prepare` has
        finished, which is the last step before the answer model is called. The route's
        dependency reads it to tell a turn that failed in preparation from one that did not.
    """

    client: UserApiClient
    retriever: DocsRetriever
    sources: SourceRegistry
    tool_outputs: list[str]
    current_project_id: str | None
    locale: str
    data_values: list[str] = field(default_factory=list)
    text_copies: list[str] = field(default_factory=list)
    roster: TurnRoster = field(default_factory=TurnRoster)
    prepared: bool = False
