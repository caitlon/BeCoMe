"""Query the document index: dense and BM25 search, with optional reranking.

"hybrid" mode and every query_transform but "none" are not implemented in this pull
request; DocsRetriever raises NotImplementedError for them at construction time.
"""

import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
from rank_bm25 import BM25Okapi

from api.assistant.rag.models import LlamaServerReranker

#: Unicode-aware by default for str patterns in Python 3, so Czech diacritics count
#: as word characters (verified directly, 2026-09-14).
_TOKEN_PATTERN = re.compile(r"\w+")

#: Generous upper bound on a lab-scale corpus's chunk count (the whole document
#: collection this project indexes is a few thousand chunks at most). BM25 needs
#: every document in the collection, not a vector-similarity subset of it.
_BM25_FETCH_LIMIT = 10_000


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens for BM25, used to score the corpus and the query alike.

    :param text: Raw text.
    :return: Lowercase word tokens.
    """
    return _TOKEN_PATTERN.findall(text.lower())


@dataclass(frozen=True)
class RetrievalConfig:
    """Which retrieval mode to run, how many results, and its optional add-ons.

    :param mode: "hybrid" is not implemented in this pull request; the default stays
        "dense" until the lab's closing step sets the measured winner.
    :param k: Number of chunks to return.
    :param rerank: Whether to rerank the candidates before truncating to k.
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
    :param score: Relevance score. Higher is always more relevant: the reranker's
        own score when rerank=True, otherwise the search mode's own score. Dense
        mode (PGVectorStore's cosine relevance) ranges over [-1, 1]: 1.0 for an
        identical vector, -1.0 for a perfectly anti-correlated one. A negative
        score there is a legitimate, unremarkable result, not an error. BM25 mode
        returns the raw BM25 score, unbounded above; a document sharing no token
        with the query scores exactly 0.0.
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
            stays valid. In dense mode, search() depends on LangChain's
            relevance-score conversion (VectorStore._select_relevance_score_fn);
            PGVectorStore implements it, a bare InMemoryVectorStore does not, and
            search() then raises NotImplementedError rather than silently
            returning a score of unknown meaning. BM25 mode reads the store's
            documents directly and has no such dependency.
        :param config: mode must not be "hybrid" and query_transform must be "none"
            in this pull request; both are enforced here, at construction time.
        :param reranker: Required when config.rerank is True; ignored otherwise.
        :param llm: Unused in this pull request (query_transform="none" needs none);
            the "translate_en"/"multi_query"/"hyde" transforms need it.
        :raises NotImplementedError: If mode is "hybrid", or query_transform is not
            "none".
        :raises ValueError: If config.rerank is True but reranker is None.
        """
        if config.mode == "hybrid":
            raise NotImplementedError("retrieval mode 'hybrid' is not implemented yet")
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
        self._bm25_documents: list[Document] | None = None
        self._bm25_index: BM25Okapi | None = None

    async def _search_dense(self, query: str, fetch_k: int) -> list[tuple[Document, float]]:
        """Dense vector search over the store, scored by LangChain's relevance conversion.

        :param query: The search query.
        :param fetch_k: How many candidates to fetch.
        :return: (Document, score) pairs, most similar first.
        :raises NotImplementedError: If the store has no relevance-score conversion
            (VectorStore._select_relevance_score_fn not overridden). PGVectorStore
            has one, a bare InMemoryVectorStore does not.
        """
        # Not the public asimilarity_search_with_relevance_scores: it warns - quoting
        # the whole fetched batch, page_content included - whenever any relevance
        # score leaves [0, 1], and PGVectorStore's cosine relevance is legitimately
        # negative for an anti-correlated candidate, which would print chunk text to
        # stderr on every such search. This protected method is the same conversion
        # (_select_relevance_score_fn applied over asimilarity_search_with_score)
        # without that warning, and still raises NotImplementedError for a store with
        # no relevance function.
        return await self._store._asimilarity_search_with_relevance_scores(query, k=fetch_k)

    async def _ensure_bm25_index(self) -> None:
        """Build the BM25 index once, from every document currently in the store.

        Cached on this instance: rebuilt only the first time a bm25 (or, later,
        hybrid) search runs, not on every call. A retrieval evaluation running many
        queries against one collection would otherwise rescan the whole collection
        once per query.

        :return: None.
        :raises ValueError: If the store's collection is empty. rank_bm25 divides
            by the document count while building the index, so an empty corpus
            would otherwise raise ZeroDivisionError with no indication of the
            real cause. Also if one fetch comes back full, because a collection
            of _BM25_FETCH_LIMIT chunks or more would be indexed only in part.
        """
        if self._bm25_index is not None:
            return
        # The public asimilarity_search_with_score, not the protected
        # relevance-score method dense search uses: bm25 needs the collection's
        # documents only and discards the scores, so pgvector's
        # distance-versus-similarity convention plays no part here.
        results = await self._store.asimilarity_search_with_score(
            "assistant corpus", k=_BM25_FETCH_LIMIT
        )
        documents = [doc for doc, _ in results]
        if not documents:
            raise ValueError("cannot build a bm25 index: the store's collection is empty")
        if len(documents) >= _BM25_FETCH_LIMIT:
            raise ValueError(
                f"cannot build a complete bm25 index: the collection fills the fetch limit "
                f"of {_BM25_FETCH_LIMIT} chunks, so some chunks may be missing; raise "
                "_BM25_FETCH_LIMIT"
            )
        self._bm25_documents = documents
        self._bm25_index = BM25Okapi([_tokenize(doc.page_content) for doc in documents])

    async def _search_bm25(self, query: str, fetch_k: int) -> list[tuple[Document, float]]:
        """BM25 keyword search over every document currently in the store.

        :param query: The search query.
        :param fetch_k: How many candidates to return.
        :return: (Document, score) pairs, highest BM25 score first.
        :raises ValueError: If the store's collection is empty, or fills the fetch
            limit.
        """
        await self._ensure_bm25_index()
        if self._bm25_index is None or self._bm25_documents is None:
            raise RuntimeError("unreachable: _ensure_bm25_index always sets both or raises")
        scores = self._bm25_index.get_scores(_tokenize(query))
        ranked = sorted(
            zip(self._bm25_documents, scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [(doc, float(score)) for doc, score in ranked[:fetch_k]]

    async def _apply_rerank(
        self, query: str, candidates: list[tuple[Document, float]]
    ) -> list[tuple[Document, float]]:
        """Rerank candidates, dense or bm25, with the configured LlamaServerReranker.

        :param query: The search query.
        :param candidates: (Document, score) pairs from dense or bm25 search.
        :return: The same documents, reordered and rescored by the reranker.
        """
        if self._reranker is None:
            raise RuntimeError("unreachable: config.rerank requires a reranker")
        texts = [doc.page_content for doc, _ in candidates]
        rerank_scores = await self._reranker.rerank(query, texts)
        return sorted(
            zip((doc for doc, _ in candidates), rerank_scores, strict=True),
            key=lambda pair: pair[1],
            reverse=True,
        )

    async def search(self, query: str) -> list[RetrievedChunk]:
        """Search the index and return the top-k chunks, most relevant first.

        Errors are not caught here: an unreachable store or reranker raises as-is.
        The chat endpoint's service layer is what turns either into
        AssistantUnavailableError.

        :param query: The search query.
        :return: Up to config.k RetrievedChunk, ordered by relevance (highest
            score, most relevant, first).
        :raises NotImplementedError: If mode is "dense" and the store has no
            relevance-score conversion (VectorStore._select_relevance_score_fn not
            overridden). PGVectorStore has one, a bare InMemoryVectorStore does not.
        :raises ValueError: If mode is "bm25" and the store's collection is empty or
            fills the fetch limit.
        """
        fetch_k = self._config.k * 4 if self._config.rerank else self._config.k
        if self._config.mode == "dense":
            candidates = await self._search_dense(query, fetch_k)
        else:
            candidates = await self._search_bm25(query, fetch_k)
        if self._config.rerank and candidates:
            candidates = await self._apply_rerank(query, candidates)
        return [
            RetrievedChunk(
                text=doc.page_content,
                title=doc.metadata["title"],
                section=doc.metadata["heading_path"],
                url=doc.metadata["url"],
                layer=doc.metadata["layer"],
                score=float(score),
            )
            for doc, score in candidates[: self._config.k]
        ]
