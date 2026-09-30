"""Per-request context threaded through the agent, and the registry of cited sources."""

from dataclasses import dataclass

from api.assistant.client import UserApiClient
from api.assistant.rag.retrieval import DocsRetriever, RetrievedChunk
from api.schemas.assistant import SourceRef


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
                url=None if chunk.layer == "local" else chunk.url,
                layer=chunk.layer,
            )
            for number, chunk in enumerate(self._chunks, start=1)
        ]

    def texts(self) -> list[str]:
        """Return the chunks' own words, for the number check.

        No ``[n]`` markers and no titles: the digits of a marker must never count as
        grounded numbers.

        :return: The ``chunk_text`` of every registered chunk, in registration order.
        """
        return [chunk.chunk_text for chunk in self._chunks]


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
