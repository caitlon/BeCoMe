"""Unit tests for query retrieval (fakes only, no network)."""

import json
import re
import unicodedata
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Literal

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
    looks_english,
    question_language,
)

_GOLDEN_SET = Path(__file__).parents[5] / "scripts" / "assistant" / "golden_set.jsonl"


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
            text="x", title="T", section="S", url=None, layer="public", score=1.0, chunk_text="x"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            chunk.score = 0.0


class TestRetrievedChunkOwnText:
    """DocsRetriever exposes the chunk's own text apart from the full indexed text."""

    @staticmethod
    async def _search_one(
        document: Document, mode: Literal["bm25", "dense", "hybrid"] = "dense"
    ) -> RetrievedChunk:
        """Index one document and return the single chunk a search in `mode` finds."""
        store = _RelevanceScoredInMemoryVectorStore(DeterministicFakeEmbedding(size=16))
        await store.aadd_documents([document])
        config = RetrievalConfig(mode=mode, k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)
        results = await retriever.search(document.page_content)
        assert len(results) == 1
        return results[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid"])
    async def test_a_captioned_document_yields_its_own_text_apart_from_the_caption(self, mode):
        """
        GIVEN an indexed document whose page_content starts with a caption and whose
              metadata carries the chunk's own text as chunk_text
        WHEN search() returns it, in dense, bm25 or hybrid (fused) mode
        THEN chunk_text is the own text alone and text is still the full indexed text
        """
        # GIVEN
        own_text = "BeCoMe combines the arithmetic mean and the median."
        indexed_text = f"Method. Introduces the aggregation method.\n\n{own_text}"
        document = _doc(indexed_text, title="Method")
        document.metadata["chunk_text"] = own_text

        # WHEN
        chunk = await self._search_one(document, mode)

        # THEN
        assert chunk.chunk_text == own_text
        assert chunk.text == indexed_text

    @pytest.mark.asyncio
    async def test_a_document_without_chunk_text_metadata_falls_back_to_page_content(self):
        """
        GIVEN an indexed document from a collection built before chunk_text was stored,
              so its metadata has no chunk_text and its page_content holds a blank-line
              paragraph break
        WHEN search() returns it
        THEN chunk_text is the whole page_content, paragraph break included
        """
        # GIVEN
        content = "First paragraph of the chunk.\n\nSecond paragraph of the chunk."
        document = _doc(content, title="Plain")

        # WHEN
        chunk = await self._search_one(document)

        # THEN
        assert chunk.chunk_text == content
        assert chunk.text == content


class TestRetrievedChunkLayer:
    """DocsRetriever passes the two known layers through and refuses anything else."""

    @staticmethod
    async def _search_with_layer(layer: str) -> list[RetrievedChunk]:
        """Index one document stored under `layer` and search for it."""
        document = _doc("A chunk of the source.", title="Layered")
        document.metadata["layer"] = layer
        store = _RelevanceScoredInMemoryVectorStore(DeterministicFakeEmbedding(size=16))
        await store.aadd_documents([document])
        config = RetrievalConfig(mode="dense", k=1, query_transform="none")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)
        return await retriever.search(document.page_content)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("layer", ["public", "local"])
    async def test_a_known_layer_comes_back_unchanged(self, layer):
        """
        GIVEN an indexed document stored under a known layer
        WHEN search() returns it
        THEN the chunk carries that layer
        """
        # WHEN
        results = await self._search_with_layer(layer)

        # THEN
        assert [chunk.layer for chunk in results] == [layer]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("layer", ["secret", "locl", "", None])
    async def test_an_unknown_layer_raises_naming_the_value(self, layer):
        """
        GIVEN an indexed document whose layer metadata is not "public" or "local"
        WHEN search() returns it
        THEN it raises a ValueError naming the bad value instead of passing it on
        """
        # WHEN / THEN
        with pytest.raises(ValueError, match=re.escape(repr(layer))):
            await self._search_with_layer(layer)


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


class TestQuestionLanguage:
    """question_language: Czech or English when sure, None otherwise."""

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Co znamená High Confidence u mého projektu?", id="quotes-label"),
            pytest.param("Co znamena High Confidence u meho projektu?", id="quotes-no-accents"),
            pytest.param("Proč má můj projekt nízkou shodu?", id="diacritics"),
            pytest.param("Jak se počítá nejlepší kompromis?", id="how"),
            pytest.param("vysvetli mi, co je maximalni chyba", id="no-diacritics-words"),
            pytest.param("Jaky je rozdil mezi prumerem a medianem", id="no-diacritics-jaky"),
            pytest.param("Proc ma muj projekt nizkou shodu?", id="no-diacritics-proc"),
            pytest.param("Řekni mi víc", id="one-czech-letter"),
            pytest.param("Vysvětlete medián", id="two-czech-letters"),
            pytest.param("Jak se počítá the median", id="czech-with-the"),
            pytest.param("Jak se pocita best of both", id="two-czech-words-no-accents"),
            pytest.param("Co znamena the median?", id="two-czech-words-and-the"),
            pytest.param("Vysvětlete fuzzy čísla and alpha řezy", id="accents-outscore-and"),
        ],
    )
    def test_czech_questions_are_czech(self, query):
        """
        GIVEN Czech questions, with and without diacritics, some quoting English terms
        WHEN question_language runs
        THEN it returns "cs"
        """
        assert question_language(query) == "cs"

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("What does High Confidence mean for my project?", id="quotes-label"),
            pytest.param("how is the best compromise calculated", id="lowercase"),
            pytest.param("Why is the maximum error so low?", id="why"),
            pytest.param("Can you explain the median?", id="can"),
            pytest.param("Which experts have not submitted an opinion?", id="which"),
            pytest.param("Explain the difference between the mean and the median", id="the"),
            pytest.param("WHAT IS THE AGREEMENT LEVEL", id="uppercase"),
            pytest.param("How many experts are in my project?", id="how"),
            pytest.param("What does Novák's estimate mean?", id="czech-surname"),
            pytest.param("Does the panel agree with Šimůnek?", id="czech-surname-2"),
            pytest.param("Compare Novák and Dvořák, which is the higher?", id="two-surnames"),
            pytest.param("I like the café menu, does it have the soup?", id="acute-vowel"),
        ],
    )
    def test_english_questions_are_english(self, query):
        """
        GIVEN English questions, some naming a Czech person or using an accented word
        WHEN question_language runs
        THEN it returns "en"
        """
        assert question_language(query) == "en"

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Popište výpočet MaxAgM for the median", id="tie-two-two"),
            pytest.param("Explain the median", id="one-english-word"),
            pytest.param("Compare Novák and Dvořák", id="one-english-word-two-surnames"),
            pytest.param("I like the café menu", id="one-english-word-acute-vowel"),
            pytest.param("Novák's estimate seems too high, why?", id="one-english-word-surname"),
            pytest.param("Was ist der Median und wie wird er berechnet?", id="german-was-wird"),
            pytest.param("Jak funguje for loop", id="tie-one-one"),
            pytest.param("Kolik expertu odpovedelo?", id="one-czech-word-no-accents"),
            pytest.param("kde najdu vysledky projektu", id="one-czech-word-no-accents-2"),
            pytest.param("Explain the průměr", id="tie-one-one-accent"),
            pytest.param("What does proč mean?", id="tie-two-two-word"),
            pytest.param("Show résumé stats", id="french-word"),
            pytest.param("Summarize Novák's opinion", id="lone-accented-name"),
            pytest.param("Show Šimůnek's estimate", id="lone-czech-name"),
            pytest.param("Explain Dvořák's range", id="lone-czech-name-2"),
            pytest.param("Explain NA values", id="na-acronym"),
            pytest.param("Show SE", id="se-acronym"),
            pytest.param("Show Jake's estimate", id="english-name"),
            pytest.param("CO JE MEDIÁN?", id="capitals-only"),
            pytest.param("BeCoMe?", id="no-words"),
            pytest.param("¿Cómo se calcula el mejor compromiso?", id="spanish"),
            pytest.param("Qu'est-ce que la méthode BeCoMe?", id="french"),
            pytest.param("Como é calculado o compromisso?", id="portuguese"),
            pytest.param("Jak obliczyć kompromis?", id="polish"),
            pytest.param("Aký je rozdiel medzi priemerom a mediánom?", id="slovak"),
            pytest.param("Wie funktioniert die Methode von BeCoMe?", id="german"),
            pytest.param("Как считается лучший компромисс?", id="russian"),
        ],
    )
    def test_a_question_that_is_not_recognisably_czech_or_english_has_none(self, query):
        """
        GIVEN ties between the two languages, a Czech question with one function word and no
              accent, a lone accented name, acronyms and English names that are also Czech
              words, capitals, and questions in other languages
        WHEN question_language runs
        THEN it returns None, so no line is added and the system prompt's rule applies
        """
        assert question_language(query) is None

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Please answer in Czech: what is the median?", id="in-czech"),
            pytest.param("Please answer in German: what is the median?", id="in-german"),
            pytest.param("Explain in Czech what the median is", id="explain-in-czech"),
            pytest.param("Tell me in Czech: what is the median?", id="tell-me-in-czech"),
            pytest.param("Could you reply to me in English? Co je medián?", id="reply-to-me"),
            pytest.param("Vysvětli mi to prosím anglicky: co je medián?", id="prosim-anglicky"),
            pytest.param("Řekni mi anglicky, co je medián", id="rekni-anglicky"),
            pytest.param("Přelož to do angličtiny: co je medián", id="do-anglictiny"),
            pytest.param("Odpověz mi\nanglicky", id="newline"),
            pytest.param("Odpověz rusky, co je medián?", id="rusky"),
            pytest.param("Odpověz anglicky: co je medián?", id="anglicky"),
            pytest.param("Odpovez cesky: what is the median", id="cesky"),
            pytest.param("Odpověz německy, co je medián?", id="nemecky"),
            pytest.param("Napiš to v angličtině", id="v-anglictine"),
            pytest.param("Co je medián? Odpověz v češtině.", id="v-cestine"),
            pytest.param("Co je medián? Odpověz v anglictine.", id="v-anglictine-plain"),
            pytest.param("Odpověz v cestine, co je medián?", id="v-cestine-plain"),
            pytest.param(
                "Explain the Czech case study and how the panel was chosen", id="czech-case-study"
            ),
        ],
    )
    def test_a_question_that_names_the_answer_language_has_none(self, query):
        """
        GIVEN questions that hold a language name anywhere, whatever the phrasing: a request
              for an answer language in either language, a request split over two lines, and
              one that only talks about a language ("the Czech case study", an accepted cost)
        WHEN question_language runs
        THEN it returns None, so the request stands and no line is added
        """
        assert question_language(query) is None

    def test_a_slovak_question_with_czech_letters_is_taken_for_czech(self):
        """
        GIVEN a Slovak question that holds letters Slovak shares with Czech
        WHEN question_language runs
        THEN it returns "cs": the closeness of the two languages is an accepted limit
        """
        assert question_language("Prečo je zhoda nízka?") == "cs"

    def test_a_decomposed_czech_question_is_czech(self):
        """
        GIVEN a Czech question typed with decomposed characters (a base letter and a
              combining mark, as some keyboards and copy-paste sources produce)
        WHEN question_language runs
        THEN it is normalised first and returns "cs"
        """
        question = unicodedata.normalize("NFD", "Vysvětlete medián")

        assert question != "Vysvětlete medián"
        assert question_language(question) == "cs"

    def test_a_three_letter_czech_word_in_capitals_still_counts(self):
        """
        GIVEN two Czech function words of three letters, written in capitals
        WHEN question_language runs
        THEN they count, so the question is Czech; only words of up to two letters (SE, NA)
             are taken for acronyms
        """
        assert question_language("JAK KDY") == "cs"

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Jak se pocita best of both", id="czech-without-accents"),
            pytest.param("Co znamena the median?", id="czech-without-accents-2"),
        ],
    )
    def test_it_calls_a_czech_question_czech_where_looks_english_does_not(self, query):
        """
        GIVEN a Czech question typed without diacritics, with English words
        WHEN looks_english and question_language run
        THEN looks_english says English, which is right for skipping a translation it
             cannot gain from, and question_language says Czech, because more of the
             words are Czech
        """
        assert looks_english(query) is True
        assert question_language(query) == "cs"

    def test_it_agrees_with_the_language_of_every_golden_set_question(self):
        """
        GIVEN the questions of the golden set, each with its language
        WHEN question_language runs on each
        THEN a Czech question is "cs" and an English one is "en" or None, because an English
             question with one function word gets no line, and none is ever labelled with
             the wrong language
        """
        rows = [
            json.loads(line)
            for line in _GOLDEN_SET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        assert rows
        for row in rows:
            expected = {row["lang"]} if row["lang"] == "cs" else {"en", None}
            assert question_language(row["question"]) in expected, row["id"]


class TestLooksEnglish:
    """looks_english: no Czech diacritics and at least one English function word."""

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("What is the best compromise in the BeCoMe method?", id="what-is-the"),
            pytest.param("how does the median differ from the mean", id="lowercase"),
            pytest.param("WHICH opinions count?", id="uppercase"),
        ],
    )
    def test_english_sentences_with_function_words_are_english(self, query):
        """
        GIVEN English questions with function words such as the, what, how, does, which
        WHEN looks_english runs
        THEN it returns True, whatever the letter case
        """
        assert looks_english(query) is True

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Co znamená what nízká hodnota Δmax?", id="cs-diacritics"),
            pytest.param("Jak se počítá the nejlepší kompromis?", id="cs-diacritics-2"),
            pytest.param("Řekni mi what is the median", id="czech-letter-in-english"),
        ],
    )
    def test_a_czech_diacritic_anywhere_makes_it_not_english(self, query):
        """
        GIVEN queries that each contain an English function word and a Czech diacritic letter
        WHEN looks_english runs
        THEN it returns False, so the diacritic check alone decides these
        """
        assert looks_english(query) is False

    def test_decomposed_czech_diacritics_are_recognised(self):
        """
        GIVEN a Czech question with an English function word, typed with decomposed
              characters (a base letter followed by a combining mark, as some keyboards
              and copy-paste sources produce)
        WHEN looks_english runs
        THEN it returns False, the same as for the precomposed spelling
        """
        decomposed = unicodedata.normalize("NFD", "Jak se počítá the kompromis?")

        assert decomposed != "Jak se počítá the kompromis?"
        assert looks_english(decomposed) is False

    def test_czech_typed_without_diacritics_is_not_english(self):
        """
        GIVEN a Czech question typed without diacritics and with no English function word
        WHEN looks_english runs
        THEN it returns False, so it still goes to translation
        """
        assert looks_english("Jak se pocita nejlepsi kompromis v metode BeCoMe?") is False

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Jak funguje BeCoMe pro IT?", id="acronym-it"),
            pytest.param("Co je IS?", id="acronym-is"),
            pytest.param("Jak WHO definuje pandemii?", id="acronym-who"),
        ],
    )
    def test_czech_without_diacritics_but_with_an_english_looking_acronym_is_not_english(
        self, query
    ):
        """
        GIVEN a Czech question typed without diacritics that contains the acronym IT, IS or WHO
        WHEN looks_english runs
        THEN it returns False, because "it", "is" and "who" are not in the function-word list
        """
        assert looks_english(query) is False

    def test_a_query_with_no_function_word_is_not_english(self):
        """
        GIVEN a bare keyword query with no function word at all
        WHEN looks_english runs
        THEN it returns False, because the rule needs an English function word
        """
        assert looks_english("BeCoMe compromise median") is False

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("Do I add a to i?", id="a-i-to-do"),
            pytest.param("On by no my", id="my-on-by-no"),
        ],
    )
    def test_words_shared_with_czech_do_not_count(self, query):
        """
        GIVEN queries made only of words that also exist in Czech (a, i, to, do; my, on,
              by, no), the second one a Czech-looking phrase typed without diacritics
        WHEN looks_english runs
        THEN it returns False, because those words are excluded from the function-word list
        """
        assert looks_english(query) is False

    def test_empty_query_is_not_english(self):
        """
        GIVEN an empty query
        WHEN looks_english runs
        THEN it returns False
        """
        assert looks_english("") is False

    def test_golden_set_english_is_recognised_and_czech_is_not(self):
        """
        GIVEN the committed golden set
        WHEN looks_english runs over every question
        THEN no Czech question is judged English, and most English ones are. The English
             side asserts a floor, not an exact count: the rule may miss an English question
             (one that carries a Czech name, or has no function word), and the set will grow.
        """
        rows = [
            json.loads(line)
            for line in _GOLDEN_SET.read_text(encoding="utf-8").splitlines()
            if line
        ]
        english = [looks_english(row["question"]) for row in rows if row["lang"] == "en"]
        czech = [looks_english(row["question"]) for row in rows if row["lang"] == "cs"]

        assert czech
        assert not any(czech)
        assert english
        assert sum(english) / len(english) >= 0.9


class TestTranslateEnSkipsEnglishQueries:
    """translate_en spends a chat-model call only on questions that are not English."""

    @pytest.mark.asyncio
    async def test_an_english_query_is_searched_as_is_without_calling_the_model(self):
        """
        GIVEN query_transform="translate_en" and a model that records every call
        WHEN _transformed_queries runs with an English question
        THEN the question comes back unchanged and the model was never called
        """
        # GIVEN
        store = InMemoryVectorStore(DeterministicFakeEmbedding(size=16))
        llm = _RecordingFakeChatModel(responses=["should not be used"])
        config = RetrievalConfig(mode="dense", query_transform="translate_en")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("What does BeCoMe combine?")

        # THEN
        assert queries == ["What does BeCoMe combine?"]
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_a_czech_query_is_still_translated(self):
        """
        GIVEN query_transform="translate_en" and a model that records every call
        WHEN _transformed_queries runs with a Czech question
        THEN the model is called once and its translation is what gets searched
        """
        # GIVEN
        store = InMemoryVectorStore(DeterministicFakeEmbedding(size=16))
        llm = _RecordingFakeChatModel(responses=["What does BeCoMe combine?"])
        config = RetrievalConfig(mode="dense", query_transform="translate_en")
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        queries = await retriever._transformed_queries("Co kombinuje BeCoMe?")

        # THEN
        assert queries == ["What does BeCoMe combine?"]
        assert llm.call_count == 1


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


class _RecordingFakeChatModel(FakeListChatModel):
    """FakeListChatModel that also remembers the temperature of its last call."""

    recorded_temperature: float | None = None
    call_count: int = 0

    def _call(self, *args, **kwargs) -> str:
        self.call_count += 1
        self.recorded_temperature = kwargs.get("temperature")
        return super()._call(*args, **kwargs)


class TestQueryTransformsRunAtZeroTemperature:
    """Every query_transform must produce the same search query for the same question.

    A transform that samples would translate, paraphrase, or hypothesize differently
    across otherwise-identical searches, so the same user question could retrieve
    different chunks from one run to the next.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("query_transform", "response"),
        [
            pytest.param("translate_en", "What does BeCoMe combine?", id="translate_en"),
            pytest.param(
                "multi_query",
                "How does BeCoMe aggregate opinions?\nWhat is the BeCoMe formula?",
                id="multi_query",
            ),
            pytest.param("hyde", "BeCoMe combines the arithmetic mean and the median.", id="hyde"),
        ],
    )
    async def test_transform_invokes_the_model_with_temperature_zero(
        self, query_transform, response
    ):
        """
        GIVEN a chat model that records the keyword arguments of its last call
        WHEN _transformed_queries runs, for each of translate_en, multi_query, and hyde
        THEN the model was called with temperature=0, so the same question always
             becomes the same search query
        """
        # GIVEN
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        llm = _RecordingFakeChatModel(responses=[response])
        config = RetrievalConfig(mode="dense", query_transform=query_transform)
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=llm)

        # WHEN
        await retriever._transformed_queries("Co kombinuje BeCoMe?")

        # THEN
        assert llm.recorded_temperature == 0


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
