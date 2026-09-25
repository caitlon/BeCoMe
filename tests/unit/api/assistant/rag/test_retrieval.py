"""Unit tests for query retrieval (fakes only, no network)."""

import warnings
from collections.abc import Callable

import httpx
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.vectorstores import InMemoryVectorStore

from api.assistant.rag.models import LlamaServerReranker
from api.assistant.rag.retrieval import (
    DocsRetriever,
    RetrievalConfig,
    RetrievedChunk,
    _reciprocal_rank_fusion,
)


def _doc(text: str, title: str, heading_path: str = "") -> Document:
    """A Document with the metadata keys DocsRetriever maps onto RetrievedChunk."""
    return Document(
        page_content=text,
        metadata={
            "title": title,
            "heading_path": heading_path,
            "url": None,
            "layer": "public",
            "source": "docs/method-description.md",
        },
    )


class _RelevanceScoredInMemoryVectorStore(InMemoryVectorStore):
    """InMemoryVectorStore, with LangChain's relevance-score hook implemented.

    InMemoryVectorStore declares no _select_relevance_score_fn, so a bare instance
    makes DocsRetriever.search() raise NotImplementedError (see
    TestDocsRetrieverDenseSearch.test_a_store_with_no_relevance_score_support_raises
    below) - correct for a real store that cannot say what its raw score means, but
    these tests need a working relevance score to exercise search() at all. The
    identity function is the right one here, not a rescale: InMemoryVectorStore's
    similarity_search_with_score already returns cosine similarity directly, the same
    [-1, 1] scale and meaning as PGVectorStore's own relevance score (1 - cosine
    distance, which equals cosine similarity) - both can legitimately go negative for
    an anti-correlated candidate, and this double should behave the same way the real
    store does.
    """

    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        return lambda similarity: similarity


class TestRetrievedChunk:
    """RetrievedChunk is the frozen dataclass the contract fixes."""

    def test_is_frozen(self):
        """
        GIVEN a constructed RetrievedChunk
        WHEN a field is assigned after construction
        THEN it raises, since retrieved chunks are immutable
        """
        import dataclasses

        chunk = RetrievedChunk(
            text="x", title="T", section="S", url=None, layer="public", score=1.0
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            chunk.score = 0.0


class TestRetrievalConfigDefaults:
    """RetrievalConfig's defaults are the search lab's measured winner, not a placeholder."""

    def test_defaults_are_the_measured_winner(self):
        """
        GIVEN a RetrievalConfig built with no arguments
        WHEN compared to the search lab's measured winner (hybrid search, k=5, no
             reranker, the query translated to English first)
        THEN the two are equal, since that combination is what every field defaults to
        """
        assert RetrievalConfig() == RetrievalConfig(
            mode="hybrid", k=5, rerank=False, query_transform="translate_en"
        )


class TestDocsRetrieverDenseSearch:
    """Dense search against an in-memory store standing in for PGVectorStore."""

    @pytest.mark.asyncio
    async def test_an_exact_text_match_comes_back_with_its_metadata_mapped(self):
        """
        GIVEN a store with one document matching the query text exactly
        WHEN search() runs in dense mode
        THEN that chunk comes back first, with title/section/url/layer mapped from
             its metadata and a near-1.0 cosine score (identical text, identical vector)
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        query_text = "BeCoMe combines the arithmetic mean and the median."
        await store.aadd_documents(
            [
                _doc(query_text, title="Method", heading_path="Overview"),
                _doc(
                    "The frontend uses React and TypeScript.",
                    title="Frontend",
                    heading_path="Stack",
                ),
            ]
        )
        config = RetrievalConfig(mode="dense", k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        results = await retriever.search(query_text)

        # THEN
        assert len(results) == 1
        assert results[0].text == query_text
        assert results[0].title == "Method"
        assert results[0].section == "Overview"
        assert results[0].url is None
        assert results[0].layer == "public"
        assert results[0].score > 0.99

    @pytest.mark.asyncio
    async def test_k_bounds_the_number_of_results(self):
        """
        GIVEN a store with three documents
        WHEN search() runs with k=2
        THEN exactly two RetrievedChunk come back
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc(f"chunk {i}", title=f"T{i}") for i in range(3)])
        config = RetrievalConfig(mode="dense", k=2, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        results = await retriever.search("chunk 1")

        # THEN
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_best_match_scores_highest_and_results_are_descending(self):
        """
        GIVEN a store with an exact-match document and two unrelated ones
        WHEN search() runs in dense mode over all three
        THEN the exact-match document's score is the highest of the three, and the
             scores come back in descending order (best match first)
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        query_text = "BeCoMe combines the arithmetic mean and the median."
        await store.aadd_documents(
            [
                _doc("The frontend uses React and TypeScript.", title="Frontend"),
                _doc(query_text, title="Method"),
                _doc("Cats are small domesticated carnivorous mammals.", title="Unrelated"),
            ]
        )
        config = RetrievalConfig(mode="dense", k=3, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        results = await retriever.search(query_text)

        # THEN
        scores = [chunk.score for chunk in results]
        assert results[0].title == "Method"
        assert results[0].score == max(scores)
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_a_store_with_no_relevance_score_support_raises(self):
        """
        GIVEN a bare InMemoryVectorStore, which declares no relevance-score
             conversion (unlike PGVectorStore, which does)
        WHEN search() runs in dense mode
        THEN it raises NotImplementedError rather than silently treating the store's
             raw score as if it meant "higher is more relevant" - a store that
             cannot say what its score means must fail loudly, not guess
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc("chunk", title="T")])
        config = RetrievalConfig(mode="dense", k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN / THEN
        with pytest.raises(NotImplementedError):
            await retriever.search("chunk")

    @pytest.mark.asyncio
    async def test_a_negative_relevance_score_emits_no_range_warning(self):
        """
        GIVEN a document with a clearly negative cosine similarity to the query -
             an anti-correlated candidate, which a cosine relevance score legitimately
             allows (see RetrievedChunk.score)
        WHEN search() runs in dense mode
        THEN no "Relevance scores must be between 0 and 1" warning fires - that
             warning would quote the whole fetched batch, page_content included, to
             stderr, outside the app's scrubbed logger - and at least one returned
             score is genuinely negative, so the check is not vacuous
        """
        # GIVEN: this document's DeterministicFakeEmbedding(size=16) vector has cosine
        # similarity ~-0.56 to the query text below (found with a one-off probe).
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        query_text = "BeCoMe combines the arithmetic mean and the median."
        await store.aadd_documents(
            [
                _doc(query_text, title="Method"),
                _doc(
                    "Deep sea creatures adapt to extreme pressure and total darkness.",
                    title="Unrelated",
                ),
            ]
        )
        config = RetrievalConfig(mode="dense", k=2, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            results = await retriever.search(query_text)

        # THEN
        assert not any(
            "Relevance scores must be between 0 and 1" in str(warning.message) for warning in caught
        )
        assert any(chunk.score < 0 for chunk in results)


class _RerankByPositionResponse:
    """Stands in for httpx.Response: index i always scores i (last candidate wins)."""

    def __init__(self, n: int) -> None:
        self._n = n

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"results": [{"index": i, "relevance_score": float(i)} for i in range(self._n)]}


class _RerankByPositionClient:
    """Records the documents it was asked to score, ranking the LAST one highest."""

    last_documents: list[str] | None = None

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_RerankByPositionClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url: str, json: dict) -> _RerankByPositionResponse:
        _RerankByPositionClient.last_documents = json["documents"]
        return _RerankByPositionResponse(len(json["documents"]))


class TestDocsRetrieverRerank:
    """Reranking reorders the dense candidates by the reranker's own scores."""

    @pytest.mark.asyncio
    async def test_final_order_follows_the_reranker_not_the_dense_order(self, monkeypatch):
        """
        GIVEN a fake reranker that always scores the last-listed candidate highest
        WHEN search() runs with rerank=True over three dense candidates
        THEN all three dense candidates were sent to the reranker, and the returned
             scores are in descending order exactly as the reranker produced them
        """
        # GIVEN
        monkeypatch.setattr(httpx, "AsyncClient", _RerankByPositionClient)
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc(f"chunk {i}", title=f"T{i}") for i in range(3)])
        reranker = LlamaServerReranker(base_url="http://127.0.0.1:8083/v1", model="m", timeout=5.0)
        config = RetrievalConfig(mode="dense", k=3, rerank=True, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=reranker, llm=None)

        # WHEN
        results = await retriever.search("chunk 1")

        # THEN
        assert len(_RerankByPositionClient.last_documents) == 3
        assert [chunk.score for chunk in results] == [2.0, 1.0, 0.0]

    def test_rejects_rerank_true_without_a_reranker(self):
        """
        GIVEN config.rerank=True but reranker=None
        WHEN DocsRetriever is constructed
        THEN it raises ValueError rather than failing later inside search()
        """
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        config = RetrievalConfig(mode="dense", rerank=True, query_transform="none")

        with pytest.raises(ValueError, match="reranker"):
            DocsRetriever(store=store, config=config, reranker=None, llm=None)


class TestTranslateEnTransform:
    """query_transform="translate_en" searches with the model's English translation."""

    def test_query_transform_other_than_none_requires_an_llm(self):
        """
        GIVEN query_transform="translate_en" but llm=None
        WHEN DocsRetriever is constructed
        THEN it raises ValueError rather than failing deep inside search()
        """
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        config = RetrievalConfig(mode="dense", query_transform="translate_en")

        with pytest.raises(ValueError, match="llm"):
            DocsRetriever(store=store, config=config, reranker=None, llm=None)

    @pytest.mark.asyncio
    async def test_searches_with_the_translated_query_not_the_original(self):
        """
        GIVEN a store whose only document matches an English phrase exactly
        WHEN search() runs with query_transform="translate_en" and a fake model that
             "translates" a Czech query to that exact English phrase
        THEN the document is found, proof the translated text drove the search
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        english_text = "BeCoMe combines the arithmetic mean and the median."
        await store.aadd_documents([_doc(english_text, title="Method")])
        llm = FakeListChatModel(responses=[english_text])
        config = RetrievalConfig(mode="dense", k=1, query_transform="translate_en")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        results = await retriever.search("Co kombinuje BeCoMe?")

        # THEN
        assert results[0].title == "Method"
        assert results[0].score > 0.99

    @pytest.mark.asyncio
    async def test_strips_a_think_block_from_the_translation(self):
        """
        GIVEN a fake model whose reply carries a <think>...</think> block before the
             actual translation
        WHEN _transformed_queries runs with query_transform="translate_en"
        THEN the returned query holds only the translation, with no trace of the block
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(
            responses=[
                "<think>This is Czech, translating to English.</think>\n\nWhat does BeCoMe combine?"
            ]
        )
        config = RetrievalConfig(mode="dense", query_transform="translate_en")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("Co kombinuje BeCoMe?")

        # THEN
        assert queries == ["What does BeCoMe combine?"]

    @pytest.mark.asyncio
    async def test_falls_back_to_the_original_query_on_an_empty_reply(self):
        """
        GIVEN a fake model that replies with only whitespace
        WHEN _transformed_queries runs with query_transform="translate_en"
        THEN it falls back to the original query instead of searching with an
             empty string
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(responses=["   "])
        config = RetrievalConfig(mode="dense", query_transform="translate_en")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("Co kombinuje BeCoMe?")

        # THEN
        assert queries == ["Co kombinuje BeCoMe?"]


class TestMultiQueryTransform:
    """query_transform="multi_query" searches with the original query plus paraphrases."""

    @pytest.mark.asyncio
    async def test_transformed_queries_includes_the_original_and_every_variant_line(self):
        """
        GIVEN a fake model that returns two paraphrased lines, with a blank line
             between them
        WHEN _transformed_queries runs with query_transform="multi_query"
        THEN it returns the original query followed by both variants, blank line dropped
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(
            responses=["How does BeCoMe aggregate opinions?\n\nWhat is the BeCoMe formula?\n"]
        )
        config = RetrievalConfig(mode="dense", query_transform="multi_query")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What does BeCoMe combine?")

        # THEN
        assert queries == [
            "What does BeCoMe combine?",
            "How does BeCoMe aggregate opinions?",
            "What is the BeCoMe formula?",
        ]

    @pytest.mark.asyncio
    async def test_a_document_matched_only_by_a_variant_is_still_retrieved(self):
        """
        GIVEN a model that generates one variant identical to a stored document's text
        WHEN search() runs with query_transform="multi_query" and k covers both documents
        THEN that document is present in the results, even though the ORIGINAL query
             text does not match it at all
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        exact_text = "BeCoMe combines the arithmetic mean and the median."
        await store.aadd_documents(
            [
                _doc(exact_text, title="Method"),
                _doc("The frontend uses React and TypeScript.", title="Frontend"),
            ]
        )
        llm = FakeListChatModel(responses=[exact_text])  # one variant, identical to the stored doc
        config = RetrievalConfig(mode="dense", k=2, query_transform="multi_query")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        results = await retriever.search("some unrelated original query text")

        # THEN
        assert len(results) == 2
        assert {chunk.title for chunk in results} == {"Method", "Frontend"}

    @pytest.mark.asyncio
    async def test_strips_a_think_block_before_splitting_into_variants(self):
        """
        GIVEN a fake model whose reply opens with a multi-line <think>...</think>
             block before the paraphrase lines
        WHEN _transformed_queries runs with query_transform="multi_query"
        THEN none of the reasoning lines appear among the returned queries
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(
            responses=[
                "<think>Let me think of two paraphrases\nfor this question.</think>\n\n"
                "How does BeCoMe aggregate opinions?\nWhat is the BeCoMe formula?"
            ]
        )
        config = RetrievalConfig(mode="dense", query_transform="multi_query")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What does BeCoMe combine?")

        # THEN
        assert queries == [
            "What does BeCoMe combine?",
            "How does BeCoMe aggregate opinions?",
            "What is the BeCoMe formula?",
        ]

    @pytest.mark.asyncio
    async def test_cleans_a_messy_reply_and_caps_the_variant_count(self):
        """
        GIVEN a reply with a preamble line, several different list-marker styles, two
             lines that repeat the original query once cleaned, one line that repeats
             an earlier variant once cleaned, and more than _MULTI_QUERY_MAX_VARIANTS
             distinct candidates left over
        WHEN _transformed_queries runs with query_transform="multi_query"
        THEN the preamble and every repeat are dropped, each kept line has its list
             marker removed, and at most _MULTI_QUERY_MAX_VARIANTS variants follow the
             original query, which stays first
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(
            responses=[
                "Here are three ways to ask that:\n"
                "1. How does BeCoMe aggregate expert opinions?\n"
                "2) What does BeCoMe combine?\n"
                "- What Does BeCoMe combine?\n"
                "* What is combined by BeCoMe?\n"
                "• How does BeCoMe aggregate expert opinions?\n"
                "5. What is the BeCoMe formula?\n"
                "6. Which two statistics does BeCoMe combine?"
            ]
        )
        config = RetrievalConfig(mode="dense", query_transform="multi_query")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What does BeCoMe combine?")

        # THEN
        assert queries == [
            "What does BeCoMe combine?",
            "How does BeCoMe aggregate expert opinions?",
            "What is combined by BeCoMe?",
            "What is the BeCoMe formula?",
        ]

    @pytest.mark.asyncio
    async def test_falls_back_to_just_the_original_query_on_an_empty_reply(self):
        """
        GIVEN a fake model that replies with only whitespace
        WHEN _transformed_queries runs with query_transform="multi_query"
        THEN it falls back to a single-element list holding just the original query
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(responses=["   "])
        config = RetrievalConfig(mode="dense", query_transform="multi_query")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What does BeCoMe combine?")

        # THEN
        assert queries == ["What does BeCoMe combine?"]

    @pytest.mark.asyncio
    async def test_fuses_the_paraphrase_rankings_over_hybrid_search(self, monkeypatch):
        """
        GIVEN mode="hybrid" and query_transform="multi_query", with dense and bm25
             search stubbed so the original query finds only "Frontend" and both
             paraphrases find only "Median"
        WHEN search() runs with k=1
        THEN "Median" comes back, since it leads two of the three per-query hybrid
             rankings being fused; a search that ignored the paraphrases would have
             returned "Frontend"
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        median = _doc("The median is robust to outliers.", title="Median")
        frontend = _doc("The frontend uses React and TypeScript.", title="Frontend")
        found_by_query = {
            "original question": frontend,
            "first paraphrase": median,
            "second paraphrase": median,
        }
        llm = FakeListChatModel(responses=["first paraphrase\nsecond paraphrase"])
        config = RetrievalConfig(mode="hybrid", k=1, query_transform="multi_query")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        async def _stub_search(query, fetch_k):
            return [(found_by_query[query], 1.0)]

        monkeypatch.setattr(retriever, "_search_dense", _stub_search)
        monkeypatch.setattr(retriever, "_search_bm25", _stub_search)

        # WHEN
        results = await retriever.search("original question")

        # THEN
        assert [chunk.title for chunk in results] == ["Median"]


class TestHydeTransform:
    """query_transform="hyde" searches with a model-generated hypothetical answer."""

    @pytest.mark.asyncio
    async def test_transformed_queries_is_just_the_hypothetical_answer(self):
        """
        GIVEN a fake model that returns one hypothetical answer
        WHEN _transformed_queries runs with query_transform="hyde"
        THEN it returns exactly that text, replacing rather than joining the original
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(responses=["The best compromise combines the mean and the median."])
        config = RetrievalConfig(mode="dense", query_transform="hyde")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What is the best compromise?")

        # THEN
        assert queries == ["The best compromise combines the mean and the median."]

    @pytest.mark.asyncio
    async def test_searches_with_the_hypothetical_answer_not_the_original_query(self):
        """
        GIVEN a store whose only document matches the model's hypothetical answer
             exactly, and does not match the original query text at all
        WHEN search() runs with query_transform="hyde"
        THEN that document is found with a near-1.0 score
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        hypothetical = "BeCoMe combines the arithmetic mean and the median."
        await store.aadd_documents([_doc(hypothetical, title="Method")])
        llm = FakeListChatModel(responses=[hypothetical])
        config = RetrievalConfig(mode="dense", k=1, query_transform="hyde")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        results = await retriever.search("What does BeCoMe do?")

        # THEN
        assert results[0].title == "Method"
        assert results[0].score > 0.99

    @pytest.mark.asyncio
    async def test_strips_a_think_block_from_the_hypothetical_answer(self):
        """
        GIVEN a fake model whose reply carries a <think>...</think> block before the
             actual hypothetical answer
        WHEN _transformed_queries runs with query_transform="hyde"
        THEN the returned query holds only the hypothetical answer, with no trace of
             the block
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(
            responses=[
                "<think>The user is asking about the compromise method.</think>\n\n"
                "The best compromise combines the mean and the median."
            ]
        )
        config = RetrievalConfig(mode="dense", query_transform="hyde")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What is the best compromise?")

        # THEN
        assert queries == ["The best compromise combines the mean and the median."]

    @pytest.mark.asyncio
    async def test_falls_back_to_the_original_query_on_an_empty_reply(self):
        """
        GIVEN a fake model that replies with only a think block and nothing else
        WHEN _transformed_queries runs with query_transform="hyde"
        THEN it falls back to the original query instead of searching with an
             empty string
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = FakeListChatModel(responses=["<think>Still deciding what to write.</think>"])
        config = RetrievalConfig(mode="dense", query_transform="hyde")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What is the best compromise?")

        # THEN
        assert queries == ["What is the best compromise?"]


class TestDocsRetrieverBm25Search:
    """BM25 keyword search over the whole collection, fetched once and cached."""

    @pytest.mark.asyncio
    async def test_ranks_the_keyword_match_above_the_unrelated_document(self):
        """
        GIVEN three documents, only two of which mention "median"
        WHEN search() runs with mode="bm25" for the query "median"
        THEN the two matching documents outrank the unrelated one
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents(
            [
                _doc("The median is robust to outliers in the panel.", title="Median"),
                _doc("The frontend uses React and TypeScript for the interface.", title="Frontend"),
                _doc("The median and the mean together form the compromise.", title="Compromise"),
            ]
        )
        config = RetrievalConfig(mode="bm25", k=3, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        results = await retriever.search("median")

        # THEN
        titles = [chunk.title for chunk in results]
        assert titles.index("Median") < titles.index("Frontend")
        assert titles.index("Compromise") < titles.index("Frontend")
        assert next(chunk.score for chunk in results if chunk.title == "Frontend") == 0.0

    @pytest.mark.asyncio
    async def test_reuses_the_cached_index_on_a_second_search(self):
        """
        GIVEN a retriever that has already run one bm25 search
        WHEN a second search runs against the same store
        THEN it still returns correct results without rebuilding from an empty index
             (a crude proxy: the store is not queried for "all documents" a second
             time, checked by monkeypatching the store's underlying search call)
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc("The median and the mean.", title="Median")])
        config = RetrievalConfig(mode="bm25", k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)
        await retriever.search("median")
        calls = []
        original = store.asimilarity_search_with_score

        async def _counting(*args, **kwargs):
            calls.append((args, kwargs))
            return await original(*args, **kwargs)

        store.asimilarity_search_with_score = _counting

        # WHEN
        await retriever.search("mean")

        # THEN
        assert calls == []  # the cached index served the second search; no re-fetch

    @pytest.mark.asyncio
    async def test_an_empty_collection_raises_a_clear_value_error(self):
        """
        GIVEN a store with no documents added to it
        WHEN search() runs with mode="bm25"
        THEN it raises ValueError naming the empty collection, rather than the
             ZeroDivisionError rank_bm25 raises internally when asked to index
             zero documents
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        config = RetrievalConfig(mode="bm25", k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN / THEN
        with pytest.raises(ValueError, match="empty"):
            await retriever.search("median")

    @pytest.mark.asyncio
    async def test_a_collection_that_fills_the_fetch_limit_raises(self, monkeypatch):
        """
        GIVEN a fetch limit of two and a store holding three documents
        WHEN search() runs with mode="bm25"
        THEN it raises ValueError instead of indexing the two documents one fetch
             returns, which would silently leave the third out of every bm25 result
        """
        # GIVEN
        monkeypatch.setattr("api.assistant.rag.retrieval._BM25_FETCH_LIMIT", 2)
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc(f"median chunk {i}", title=f"T{i}") for i in range(3)])
        config = RetrievalConfig(mode="bm25", k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN / THEN
        with pytest.raises(ValueError, match="fetch limit"):
            await retriever.search("median")

    @pytest.mark.asyncio
    async def test_rerank_reorders_the_bm25_candidates(self, monkeypatch):
        """
        GIVEN a fake reranker that always scores the last-listed candidate highest
        WHEN search() runs with mode="bm25" and rerank=True over three documents
        THEN all three bm25 candidates were sent to the reranker, and the returned
             scores are the reranker's own, in descending order
        """
        # GIVEN
        monkeypatch.setattr(httpx, "AsyncClient", _RerankByPositionClient)
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc(f"median chunk {i}", title=f"T{i}") for i in range(3)])
        reranker = LlamaServerReranker(base_url="http://127.0.0.1:8083/v1", model="m", timeout=5.0)
        config = RetrievalConfig(mode="bm25", k=3, rerank=True, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=reranker, llm=None)

        # WHEN
        results = await retriever.search("median")

        # THEN
        assert len(_RerankByPositionClient.last_documents) == 3
        assert [chunk.score for chunk in results] == [2.0, 1.0, 0.0]


def _rrf_score(k: int, *ranks: int) -> float:
    """The expected reciprocal rank fusion score for a document at these ranks.

    One rank per ranking the document appears in, computed from the same formula
    _reciprocal_rank_fusion uses, so a test's expected score is never a hand-typed
    total that could itself be wrong.
    """
    return sum(1 / (k + rank + 1) for rank in ranks)


class TestReciprocalRankFusion:
    """RRF combines rankings by position, not by their (incomparable) scores."""

    def test_fuses_two_orderings_by_rank_position(self):
        """
        GIVEN dense order [A, B, C] and bm25 order [B, C, A], k=60
        WHEN _reciprocal_rank_fusion combines them
        THEN the fused order is B, A, C, matching the rank-formula scores: A is rank 0
             in dense and rank 2 in bm25, B is rank 1 in dense and rank 0 in bm25, C is
             rank 2 in dense and rank 1 in bm25
        """
        # GIVEN
        doc_a = _doc("text a", title="A")
        doc_b = _doc("text b", title="B")
        doc_c = _doc("text c", title="C")
        dense = [(doc_a, 0.9), (doc_b, 0.8), (doc_c, 0.7)]
        bm25 = [(doc_b, 5.0), (doc_c, 4.0), (doc_a, 1.0)]

        # WHEN
        fused = _reciprocal_rank_fusion([dense, bm25], k=60)

        # THEN
        assert [doc.metadata["title"] for doc, _ in fused] == ["B", "A", "C"]
        assert round(fused[0][1], 6) == round(_rrf_score(60, 1, 0), 6)

    def test_a_document_in_only_one_ranking_still_scores(self):
        """
        GIVEN a document that appears only in the second of two rankings
        WHEN _reciprocal_rank_fusion combines an empty ranking with it
        THEN it still appears in the fused result, scored from that one ranking alone
        """
        # GIVEN
        doc = _doc("bm25 only", title="Only")

        # WHEN
        fused = _reciprocal_rank_fusion([[], [(doc, 3.0)]], k=60)

        # THEN
        assert len(fused) == 1
        assert fused[0][0].metadata["title"] == "Only"
        assert round(fused[0][1], 6) == round(_rrf_score(60, 0), 6)

    def test_fuses_more_than_two_rankings(self):
        """
        GIVEN three rankings, each led by a different document
        WHEN _reciprocal_rank_fusion combines all three
        THEN a document leading in two of the three rankings outranks the others
        """
        # GIVEN
        doc_a = _doc("text a", title="A")
        doc_b = _doc("text b", title="B")
        rankings = [
            [(doc_a, 1.0), (doc_b, 0.5)],
            [(doc_b, 1.0), (doc_a, 0.5)],
            [(doc_b, 1.0), (doc_a, 0.5)],
        ]

        # WHEN
        fused = _reciprocal_rank_fusion(rankings, k=60)

        # THEN
        assert fused[0][0].metadata["title"] == "B"


class TestDocsRetrieverHybridSearch:
    """Hybrid mode fuses dense and bm25 candidates via reciprocal rank fusion."""

    @pytest.mark.asyncio
    async def test_returns_results_combining_both_search_modes(self):
        """
        GIVEN a store with a keyword-distinctive and a keyword-generic document
        WHEN search() runs with mode="hybrid"
        THEN both documents come back, and the call does not raise
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = _RelevanceScoredInMemoryVectorStore(embeddings)
        await store.aadd_documents(
            [
                _doc("The median is robust to outliers.", title="Median"),
                _doc("The frontend uses React and TypeScript.", title="Frontend"),
            ]
        )
        config = RetrievalConfig(mode="hybrid", k=2, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        results = await retriever.search("median")

        # THEN
        assert {chunk.title for chunk in results} == {"Median", "Frontend"}
