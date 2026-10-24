"""Tests for the check of the assistant's backends made when the process starts."""

import asyncio
import json
import logging

import httpx
import openai
import pytest
from pydantic import SecretStr

from api.assistant import startup
from api.assistant.errors import AssistantUnavailableError
from api.assistant.rag.models import make_answer_model
from api.assistant.rag.retrieval import RetrievalConfig
from api.assistant.roles import tag_role
from api.config import get_settings

_LOGGER = "api.assistant.startup"
_SECRET_TEXT = "http://secret-host.internal:9999/v1 sk-leaked-key"  # pragma: allowlist secret


class _FakeModel:
    """A chat model that records the options it was bound with and the prompts it got."""

    def __init__(self, error: Exception | None = None, hang: bool = False) -> None:
        self.error = error
        self.hang = hang
        self.bound: dict[str, object] = {}
        self.prompts: list[object] = []

    def bind(self, **kwargs: object) -> "_FakeModel":
        self.bound = kwargs
        return self

    async def ainvoke(self, prompt: object) -> object:
        self.prompts.append(prompt)
        if self.hang:
            await asyncio.sleep(10)
        if self.error is not None:
            raise self.error
        return object()


class _FakeEmbeddings:
    def __init__(self, error: Exception | None = None, hang: bool = False) -> None:
        self.error = error
        self.hang = hang
        self.texts: list[str] = []

    async def aembed_query(self, text: str) -> list[float]:
        self.texts.append(text)
        if self.hang:
            await asyncio.sleep(10)
        if self.error is not None:
            raise self.error
        return [0.1]


class _Backends:
    """Stand-ins for every backend the startup check reaches, all healthy until told not to be."""

    def __init__(self) -> None:
        self.answer = _FakeModel()
        self.query = _FakeModel()
        self.embeddings = _FakeEmbeddings()
        self.vector_db_error: Exception | None = None
        self.rerank_error: Exception | None = None
        self.vector_db_calls = 0
        self.rerank_calls: list[tuple[str, list[str]]] = []
        self.reranker_built = 0


@pytest.fixture
def settings():
    """Settings with the assistant on and a bound on each probe that a test can run out."""
    return get_settings().model_copy(
        update={"assistant_enabled": True, "assistant_llm_timeout_seconds": 5.0}
    )


@pytest.fixture
def backends(monkeypatch):
    """Replace every backend the check reaches; the config asks for rerank and a query model."""
    fake = _Backends()

    def get_docs_retriever():
        fake.vector_db_calls += 1
        if fake.vector_db_error is not None:
            raise fake.vector_db_error

    class _Reranker:
        def __init__(self, base_url: str, model: str, timeout: float) -> None:
            fake.reranker_built += 1

        async def rerank(self, query: str, texts: list[str]) -> list[float]:
            fake.rerank_calls.append((query, texts))
            if fake.rerank_error is not None:
                raise fake.rerank_error
            return [0.5] * len(texts)

    monkeypatch.setattr(startup, "get_docs_retriever", get_docs_retriever)
    monkeypatch.setattr(startup, "get_answer_model", lambda: fake.answer)
    monkeypatch.setattr(startup, "get_query_model", lambda: fake.query)
    monkeypatch.setattr(startup, "make_embeddings", lambda _settings: fake.embeddings)
    monkeypatch.setattr(startup, "LlamaServerReranker", _Reranker)
    _configure(monkeypatch, rerank=True, query_transform="translate_en")
    return fake


def _configure(monkeypatch, **fields) -> None:
    """Make the check read a retrieval config with the given fields."""
    monkeypatch.setattr(startup, "RetrievalConfig", lambda k: RetrievalConfig(k=k, **fields))


def _records(caplog, level: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == _LOGGER and r.levelno == level]


def _failures(caplog) -> dict[str, logging.LogRecord]:
    """The ERROR records, by the role they name."""
    return {r.role: r for r in _records(caplog, logging.ERROR)}


@pytest.mark.asyncio
class TestWhenEveryBackendAnswers:
    async def test_logs_one_summary_and_no_error(self, settings, backends, caplog):
        """
        GIVEN every backend healthy and a config that asks for a query model and a reranker
        WHEN the check runs
        THEN there is no ERROR and one INFO record counting the five backends checked
        """
        # GIVEN
        caplog.set_level(logging.INFO, logger=_LOGGER)

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        assert _records(caplog, logging.ERROR) == []
        (summary,) = _records(caplog, logging.INFO)
        assert summary.event == "assistant_backends_checked"
        assert summary.checked == 5
        assert summary.duration_ms >= 0

    async def test_sends_one_short_request_to_each_backend(self, settings, backends, caplog):
        """
        GIVEN every backend healthy
        WHEN the check runs
        THEN each got one request, and the two chat models were capped at a few tokens
        """
        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        assert backends.vector_db_calls == 1
        assert len(backends.embeddings.texts) == 1
        assert len(backends.answer.prompts) == 1
        assert len(backends.query.prompts) == 1
        assert backends.rerank_calls == [("ping", ["ping"])]
        assert backends.answer.bound == {"max_completion_tokens": 8}
        assert backends.query.bound == {"max_completion_tokens": 8}


@pytest.mark.asyncio
class TestWhenABackendFails:
    @pytest.mark.parametrize("role", ["vector_db", "embedding", "answer", "query", "rerank"])
    async def test_logs_one_error_naming_the_role(self, settings, backends, caplog, role):
        """
        GIVEN one backend that raises an error whose text names a host and a key
        WHEN the check runs
        THEN exactly one ERROR names that role and the error's class, and nothing of its text
             reaches the record; the other backends are still checked, and there is no summary
        """
        # GIVEN
        caplog.set_level(logging.INFO, logger=_LOGGER)
        error = RuntimeError(_SECRET_TEXT)
        if role == "vector_db":
            backends.vector_db_error = error
        elif role == "embedding":
            backends.embeddings.error = error
        elif role == "answer":
            backends.answer.error = error
        elif role == "query":
            backends.query.error = error
        else:
            backends.rerank_error = error

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        failures = _records(caplog, logging.ERROR)
        assert len(failures) == 1
        (record,) = failures
        assert record.event == "assistant_backend_check_failed"
        assert record.role == role
        assert record.reason == "RuntimeError"
        assert record.getMessage() == "Assistant backend check failed at startup"
        assert "secret-host" not in " ".join(str(value) for value in vars(record).values())
        assert "sk-leaked-key" not in " ".join(str(value) for value in vars(record).values())
        assert _records(caplog, logging.INFO) == []
        assert backends.vector_db_calls == 1
        assert len(backends.embeddings.texts) == 1

    async def test_names_the_vector_db_for_an_unavailable_error(self, settings, backends, caplog):
        """
        GIVEN a document index the retriever cannot open (the error carries no role)
        WHEN the check runs
        THEN the record names vector_db and the class AssistantUnavailableError
        """
        # GIVEN
        backends.vector_db_error = AssistantUnavailableError("down")

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        record = _failures(caplog)["vector_db"]
        assert record.reason == "AssistantUnavailableError"

    async def test_prefers_the_role_written_on_the_error(self, settings, backends, caplog):
        """
        GIVEN the answer probe fails with an error tagged as the embedding server's
        WHEN the check runs
        THEN the record names the tagged role, as the 503 records do
        """
        # GIVEN
        error = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
        tag_role(error, "embedding")
        backends.answer.error = error

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        assert set(_failures(caplog)) == {"embedding"}
        assert _failures(caplog)["embedding"].reason == "APIConnectionError"

    async def test_logs_a_hanging_backend_as_a_timeout(self, settings, backends, caplog):
        """
        GIVEN an embedding server that never answers and a short bound on each probe
        WHEN the check runs
        THEN the embedding gets an ERROR with reason TimeoutError, and the check returns
        """
        # GIVEN
        backends.embeddings.hang = True
        short = settings.model_copy(update={"assistant_llm_timeout_seconds": 0.05})

        # WHEN
        await asyncio.wait_for(startup.check_assistant_backends(short), timeout=5)

        # THEN
        assert set(_failures(caplog)) == {"embedding"}
        assert _failures(caplog)["embedding"].reason == "TimeoutError"

    async def test_logs_every_failing_backend(self, settings, backends, caplog):
        """
        GIVEN two backends that fail
        WHEN the check runs
        THEN each has its own ERROR
        """
        # GIVEN
        backends.answer.error = RuntimeError("a")
        backends.rerank_error = RuntimeError("b")

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        assert set(_failures(caplog)) == {"answer", "rerank"}


@pytest.mark.asyncio
class TestWhichBackendsAreChecked:
    async def test_skips_the_query_model_when_no_query_is_transformed(
        self, settings, backends, monkeypatch, caplog
    ):
        """
        GIVEN a retrieval config with no query transform
        WHEN the check runs
        THEN the query model is not asked, and the summary counts four backends
        """
        # GIVEN
        caplog.set_level(logging.INFO, logger=_LOGGER)
        _configure(monkeypatch, rerank=True, query_transform="none")

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        assert backends.query.prompts == []
        (summary,) = _records(caplog, logging.INFO)
        assert summary.checked == 4

    async def test_skips_the_reranker_when_the_config_does_not_rerank(
        self, settings, backends, monkeypatch, caplog
    ):
        """
        GIVEN a retrieval config without rerank
        WHEN the check runs
        THEN the reranker is neither built nor called, and the summary counts four backends
        """
        # GIVEN
        caplog.set_level(logging.INFO, logger=_LOGGER)
        _configure(monkeypatch, rerank=False, query_transform="translate_en")

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        assert backends.reranker_built == 0
        assert backends.rerank_calls == []
        (summary,) = _records(caplog, logging.INFO)
        assert summary.checked == 4


def _completion_cut_off_by_the_cap(request: httpx.Request) -> httpx.Response:
    """Answer like a server that hit max_completion_tokens before writing any text."""
    _completion_cut_off_by_the_cap.bodies.append(json.loads(request.content))
    return httpx.Response(
        200,
        json={
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": ""},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 8, "total_tokens": 9},
        },
    )


_completion_cut_off_by_the_cap.bodies = []  # type: ignore[attr-defined]


@pytest.mark.asyncio
class TestARealClientCutOffByTheCap:
    async def test_a_reply_cut_off_by_the_cap_is_not_a_failure(
        self, settings, backends, monkeypatch, caplog
    ):
        """
        GIVEN the real answer client, on a server whose reply is empty and stopped by the cap
        WHEN the check runs
        THEN the request carried the small cap, and the cut-off reply raised no ERROR
        """
        # GIVEN
        _completion_cut_off_by_the_cap.bodies.clear()
        # The class the factory builds, given a transport that needs no network.
        model = type(make_answer_model(settings))(
            upstream_role="answer",
            base_url="http://answer.invalid/v1",
            api_key=SecretStr("k"),  # pragma: allowlist secret
            model="m",
            max_completion_tokens=1000,
            max_retries=0,
            http_async_client=httpx.AsyncClient(
                transport=httpx.MockTransport(_completion_cut_off_by_the_cap)
            ),
        )
        monkeypatch.setattr(startup, "get_answer_model", lambda: model)

        # WHEN
        await startup.check_assistant_backends(settings)

        # THEN
        (body,) = _completion_cut_off_by_the_cap.bodies
        assert body["max_completion_tokens"] == 8
        assert _records(caplog, logging.ERROR) == []
