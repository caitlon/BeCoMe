"""Unit tests for query retrieval (fakes only, no network)."""

import httpx
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.vectorstores import InMemoryVectorStore

from api.assistant.rag.models import LlamaServerReranker
from api.assistant.rag.retrieval import DocsRetriever, RetrievalConfig, RetrievedChunk


def _doc(text: str, title: str, heading_path: str = "") -> Document:
    """A Document with the metadata keys DocsRetriever maps onto RetrievedChunk."""
    return Document(
        page_content=text,
        metadata={"title": title, "heading_path": heading_path, "url": None, "layer": "public"},
    )


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
        store = InMemoryVectorStore(embeddings)
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
        config = RetrievalConfig(mode="dense", k=1)
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
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc(f"chunk {i}", title=f"T{i}") for i in range(3)])
        config = RetrievalConfig(mode="dense", k=2)
        retriever = DocsRetriever(store=store, config=config, reranker=None, llm=None)

        # WHEN
        results = await retriever.search("chunk 1")

        # THEN
        assert len(results) == 2


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
        store = InMemoryVectorStore(embeddings)
        await store.aadd_documents([_doc(f"chunk {i}", title=f"T{i}") for i in range(3)])
        reranker = LlamaServerReranker(base_url="http://127.0.0.1:8083/v1", model="m", timeout=5.0)
        config = RetrievalConfig(mode="dense", k=3, rerank=True)
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
        store = InMemoryVectorStore(embeddings)
        config = RetrievalConfig(mode="dense", rerank=True)

        with pytest.raises(ValueError, match="reranker"):
            DocsRetriever(store=store, config=config, reranker=None, llm=None)


class TestUnimplementedRetrieval:
    """Every mode but dense, and every query_transform but none, is the retrieval
    experiments' job."""

    def test_rejects_a_mode_other_than_dense(self):
        """
        GIVEN a RetrievalConfig with mode="bm25"
        WHEN DocsRetriever is constructed
        THEN it raises NotImplementedError naming the mode
        """
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        config = RetrievalConfig(mode="bm25")

        with pytest.raises(NotImplementedError, match="bm25"):
            DocsRetriever(store=store, config=config, reranker=None, llm=None)

    def test_rejects_a_query_transform_other_than_none(self):
        """
        GIVEN a RetrievalConfig with query_transform="hyde"
        WHEN DocsRetriever is constructed
        THEN it raises NotImplementedError naming the transform
        """
        embeddings = DeterministicFakeEmbedding(size=16)
        store = InMemoryVectorStore(embeddings)
        config = RetrievalConfig(mode="dense", query_transform="hyde")

        with pytest.raises(NotImplementedError, match="hyde"):
            DocsRetriever(store=store, config=config, reranker=None, llm=None)
