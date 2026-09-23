"""Query the document index: dense vector search, with optional reranking.

Only mode="dense" and query_transform="none" are implemented in this pull request;
the retrieval experiments add "bm25", "hybrid", and the three query_transform values.
"""

from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore

from api.assistant.rag.models import LlamaServerReranker


@dataclass(frozen=True)
class RetrievalConfig:
    """Which retrieval mode to run, how many results, and its optional add-ons.

    :param mode: Only "dense" is implemented in this pull request, so it is also the
        default; the retrieval experiments replace the defaults with the measured winner.
    :param k: Number of chunks to return.
    :param rerank: Whether to rerank the dense candidates before truncating to k.
    :param query_transform: Only "none" is implemented in this pull request.
    """

    mode: Literal["bm25", "dense", "hybrid"] = "dense"
    k: int = 5
    rerank: bool = False
    query_transform: Literal["none", "translate_en", "multi_query", "hyde"] = "none"


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieved chunk, with exactly what a citation needs.

    :param text: The chunk's text.
    :param title: The source document's title.
    :param section: The chunk's heading_path metadata.
    :param url: The source's public URL, or None.
    :param layer: "public" or "local".
    :param score: Relevance score - higher is always more relevant. The reranker's
        own score when rerank=True; otherwise the vector store's relevance score.
        For PGVectorStore with cosine distance, that equals the cosine similarity
        directly and ranges over [-1, 1]: 1.0 for an identical vector, -1.0 for a
        perfectly anti-correlated one - a negative score is a legitimate,
        unremarkable result, not an error.
    """

    text: str
    title: str
    section: str
    url: str | None
    layer: str
    score: float


class DocsRetriever:
    """Retrieve document chunks relevant to a query."""

    def __init__(
        self,
        store: VectorStore,
        config: RetrievalConfig,
        reranker: LlamaServerReranker | None,
        llm: BaseChatModel | None,
    ) -> None:
        """
        :param store: The document index to search. Typed as the LangChain VectorStore
            base class, not the more specific PGVectorStore, so every real caller
            stays valid - but search() depends on LangChain's relevance-score
            conversion (VectorStore._select_relevance_score_fn). PGVectorStore
            implements it; a bare InMemoryVectorStore does not and makes search()
            raise NotImplementedError rather than silently returning a score of
            unknown meaning.
        :param config: mode must be "dense" and query_transform must be "none" in
            this pull request; both are enforced here, at construction time.
        :param reranker: Required when config.rerank is True; ignored otherwise.
        :param llm: Unused in this pull request (query_transform="none" needs none);
            the "translate_en"/"multi_query"/"hyde" transforms need it.
        :raises NotImplementedError: If mode is not "dense", or query_transform is
            not "none".
        :raises ValueError: If config.rerank is True but reranker is None.
        """
        if config.mode != "dense":
            raise NotImplementedError(
                f"retrieval mode {config.mode!r} is not implemented yet; only 'dense' "
                "ships in this pull request"
            )
        if config.query_transform != "none":
            raise NotImplementedError(
                f"query_transform {config.query_transform!r} is not implemented yet; "
                "only 'none' ships in this pull request"
            )
        if config.rerank and reranker is None:
            raise ValueError("config.rerank is True but no reranker was given")
        self._store = store
        self._config = config
        self._reranker = reranker
        self._llm = llm

    async def search(self, query: str) -> list[RetrievedChunk]:
        """Search the index and return the top-k chunks, most relevant first.

        Scores are relevance scores, not raw distances: higher is always more
        relevant, most relevant first, for every store. A store that has no
        relevance-score conversion (VectorStore._select_relevance_score_fn not
        overridden) raises NotImplementedError here instead of silently returning a
        raw score whose meaning - similarity or distance - this code cannot know.

        Errors are not caught here: an unreachable store or reranker raises as-is.
        The chat endpoint's service layer is what turns either into
        AssistantUnavailableError.

        :param query: The search query.
        :return: Up to config.k RetrievedChunk, ordered by relevance (highest
            score, most relevant, first).
        :raises NotImplementedError: If the store has no relevance-score conversion
            (VectorStore._select_relevance_score_fn not overridden) - PGVectorStore
            has one, a bare InMemoryVectorStore does not.
        """
        fetch_k = self._config.k * 4 if self._config.rerank else self._config.k
        # Not the public asimilarity_search_with_relevance_scores: it warns - quoting
        # the whole fetched batch, page_content included - whenever any relevance
        # score leaves [0, 1], and PGVectorStore's cosine relevance is legitimately
        # negative for an anti-correlated candidate, which would print chunk text to
        # stderr on every such search. This protected method is the same conversion
        # (_select_relevance_score_fn applied over asimilarity_search_with_score)
        # without that warning, and still raises NotImplementedError for a store with
        # no relevance function.
        dense_results = await self._store._asimilarity_search_with_relevance_scores(
            query, k=fetch_k
        )
        if self._config.rerank and dense_results:
            if self._reranker is None:
                raise RuntimeError("unreachable: config.rerank requires a reranker")
            texts = [doc.page_content for doc, _ in dense_results]
            rerank_scores = await self._reranker.rerank(query, texts)
            docs_and_scores = sorted(
                zip((doc for doc, _ in dense_results), rerank_scores, strict=True),
                key=lambda pair: pair[1],
                reverse=True,
            )
        else:
            docs_and_scores = list(dense_results)
        return [
            RetrievedChunk(
                text=doc.page_content,
                title=doc.metadata["title"],
                section=doc.metadata["heading_path"],
                url=doc.metadata["url"],
                layer=doc.metadata["layer"],
                score=float(score),
            )
            for doc, score in docs_and_scores[: self._config.k]
        ]
