"""Query the document index: dense search, BM25 search, and a hybrid of the two.

Hybrid mode fuses dense and BM25 rankings by reciprocal rank fusion. A query_transform
turns the query into one or more queries actually used to search: "translate_en"
searches with the model's English translation, "multi_query" adds paraphrases of the
query, and "hyde" replaces the query with a model-generated hypothetical answer.
"""

import re
from dataclasses import dataclass
from typing import Literal

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.vectorstores import VectorStore
from rank_bm25 import BM25Okapi

from api.assistant.rag.models import LlamaServerReranker, strip_think_block

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

    :param mode: "dense", "bm25", or "hybrid" (reciprocal rank fusion of the other
        two). The default stays "dense" until the lab's closing step sets the
        measured winner.
    :param k: Number of chunks to return.
    :param rerank: Whether to rerank the candidates before truncating to k.
    :param query_transform: "none", "translate_en", "multi_query", or "hyde".
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
        with the query scores exactly 0.0. Hybrid mode returns the fused reciprocal
        rank fusion score: still higher is more relevant, but on its own scale,
        small positive numbers rather than a cosine similarity or a BM25 score.
    """

    text: str
    title: str
    section: str
    url: str | None
    layer: str
    score: float


#: Reciprocal rank fusion's damping constant, from the paper that introduced it
#: (Cormack, Clarke and Buettcher, "Reciprocal Rank Fusion Outperforms Condorcet and
#: Individual Rank Learning Methods", SIGIR 2009). Also the default of
#: langchain-postgres's own reciprocal_rank_fusion function, though not of its
#: HybridSearchConfig, whose fusion_function defaults to weighted_sum_ranking
#: instead. Fusion runs in process here, over _search_dense and _search_bm25, rather
#: than through that library's built-in hybrid search: PostgreSQL ships no Czech
#: text-search configuration, so the built-in hybrid's full-text component would
#: tokenize and stem the Czech half of the corpus with English rules.
_RRF_K = 60


def _reciprocal_rank_fusion(
    rankings: list[list[tuple[Document, float]]], k: int = _RRF_K
) -> list[tuple[Document, float]]:
    """Combine any number of rankings by reciprocal rank fusion: score = sum(1 / (k + rank + 1)).

    Rank-based, not score-based: dense cosine similarity and BM25 scores live on
    different, incomparable scales, so RRF looks only at each document's position in
    each ranking. That is also why the signature takes a list of rankings rather than
    two named parameters: nothing here is specific to fusing exactly a dense and a
    bm25 ranking, only to fusing rankings in general.

    :param rankings: Any number of (Document, score) rankings to combine, each
        already sorted best-first; the score half of each pair is ignored.
    :param k: RRF's damping constant.
    :return: Fused (Document, score) pairs, highest fused score first. A document
        appearing in only one ranking is still included, scored from that one alone.
    """
    scores: dict[tuple[str, str], float] = {}
    docs_by_key: dict[tuple[str, str], Document] = {}
    for ranking in rankings:
        for rank, (doc, _) in enumerate(ranking):
            key = (str(doc.metadata.get("source", "")), doc.page_content)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            docs_by_key[key] = doc
    ranked_keys = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [(docs_by_key[key], scores[key]) for key in ranked_keys]


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
        :param config: mode may be "dense", "bm25", or "hybrid".
        :param reranker: Required when config.rerank is True; ignored otherwise.
        :param llm: Required when config.query_transform is not "none"; unused
            otherwise.
        :raises ValueError: If config.rerank is True but reranker is None, or if
            query_transform is not "none" and llm is None.
        """
        if config.query_transform != "none" and llm is None:
            raise ValueError(f"query_transform {config.query_transform!r} requires an llm")
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

        Cached on this instance: rebuilt only the first time a bm25 or hybrid search
        runs, not on every call. A retrieval evaluation running many queries against
        one collection would otherwise rescan the whole collection once per query.

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

    async def _search_hybrid(self, query: str, fetch_k: int) -> list[tuple[Document, float]]:
        """Combine dense and BM25 search via reciprocal rank fusion.

        :param query: The search query.
        :param fetch_k: How many candidates to fetch from each of dense and bm25
            search, and how many fused results to return.
        :return: Fused (Document, score) pairs, highest fused score first.
        """
        dense = await self._search_dense(query, fetch_k)
        bm25 = await self._search_bm25(query, fetch_k)
        return _reciprocal_rank_fusion([dense, bm25])[:fetch_k]

    _TRANSLATE_PROMPT = (
        "Translate the following text to English. Reply with only the translation:\n\n{query}"
    )

    async def _translate_to_english(self, query: str) -> str:
        """Ask the model to translate the query to English.

        :param query: The user's original query, in any language.
        :return: The model's English translation.
        """
        if self._llm is None:
            raise RuntimeError("unreachable: __init__ requires an llm for this query_transform")
        response = await self._llm.ainvoke(self._TRANSLATE_PROMPT.format(query=query))
        return strip_think_block(str(response.content))

    _MULTI_QUERY_VARIANTS = 3
    _MULTI_QUERY_PROMPT = (
        "Write {n} different ways to ask this same question, one per line, no "
        "numbering or extra text:\n\n{query}"
    )

    async def _multi_query_variants(self, query: str) -> list[str]:
        """Ask the model to paraphrase the query, and search with the original too.

        :param query: The user's original query.
        :return: The original query, followed by each non-blank paraphrase line.
        """
        if self._llm is None:
            raise RuntimeError("unreachable: __init__ requires an llm for this query_transform")
        prompt = self._MULTI_QUERY_PROMPT.format(n=self._MULTI_QUERY_VARIANTS, query=query)
        response = await self._llm.ainvoke(prompt)
        reply = strip_think_block(str(response.content))
        variants = [line.strip() for line in reply.splitlines() if line.strip()]
        return [query, *variants]

    _HYDE_PROMPT = (
        "Write a short, plausible passage that would answer this question, as if it "
        "came from technical documentation. Do not mention that you are guessing:\n\n{query}"
    )

    async def _hypothetical_answer(self, query: str) -> str:
        """Ask the model to write a plausible answer, to search with instead of the query.

        :param query: The user's original query.
        :return: The model's hypothetical answer text.
        """
        if self._llm is None:
            raise RuntimeError("unreachable: __init__ requires an llm for this query_transform")
        response = await self._llm.ainvoke(self._HYDE_PROMPT.format(query=query))
        return strip_think_block(str(response.content))

    async def _transformed_queries(self, query: str) -> list[str]:
        """Turn one query into the query, or queries, actually used to search.

        :param query: The user's original query.
        :return: A single query for "none", "translate_en", and "hyde" (the last
            replacing rather than joining the original); the original query plus
            paraphrases for "multi_query".
        """
        if self._config.query_transform == "translate_en":
            return [await self._translate_to_english(query)]
        if self._config.query_transform == "multi_query":
            return await self._multi_query_variants(query)
        if self._config.query_transform == "hyde":
            return [await self._hypothetical_answer(query)]
        return [query]

    async def _search_one(self, query: str, fetch_k: int) -> list[tuple[Document, float]]:
        """Run a single search in the configured mode.

        :param query: One search query: the original, or one produced by a
            query_transform.
        :param fetch_k: How many candidates to fetch.
        :return: (Document, score) pairs.
        """
        if self._config.mode == "dense":
            return await self._search_dense(query, fetch_k)
        if self._config.mode == "bm25":
            return await self._search_bm25(query, fetch_k)
        return await self._search_hybrid(query, fetch_k)

    async def search(self, query: str) -> list[RetrievedChunk]:
        """Search the index and return the top-k chunks, most relevant first.

        Errors are not caught here: an unreachable store, llm, or reranker raises
        as-is. The chat endpoint's service layer is what turns any of them into
        AssistantUnavailableError.

        :param query: The search query.
        :return: Up to config.k RetrievedChunk, ordered by relevance (highest
            score, most relevant, first).
        :raises NotImplementedError: If mode is "dense" or "hybrid" and the store has
            no relevance-score conversion (VectorStore._select_relevance_score_fn not
            overridden). PGVectorStore has one, a bare InMemoryVectorStore does not.
        :raises ValueError: If mode is "bm25" or "hybrid" and the store's collection
            is empty or fills the fetch limit.
        """
        fetch_k = self._config.k * 4 if self._config.rerank else self._config.k
        search_queries = await self._transformed_queries(query)
        rankings = [await self._search_one(one, fetch_k) for one in search_queries]
        candidates = (
            rankings[0] if len(rankings) == 1 else _reciprocal_rank_fusion(rankings)[:fetch_k]
        )
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
