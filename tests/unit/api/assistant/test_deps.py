"""Tests for the assistant's dependency factories (fakes only, no network)."""

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from sqlalchemy.exc import OperationalError

from api.assistant import deps
from api.assistant.errors import AssistantUnavailableError
from api.assistant.rag.retrieval import RetrievalConfig
from api.config import Settings
from tests.shared.helpers import captured_log_records


@pytest.fixture(autouse=True)
def _isolated_caches(monkeypatch, tmp_path):
    """Keep the factories away from the repository's .env and from each other's caches."""
    monkeypatch.chdir(tmp_path)
    deps.clear_caches()
    yield
    deps.clear_caches()


def _settings(**overrides: Any) -> Settings:
    fields: dict[str, Any] = {
        "secret_key": "test-secret-key",  # pragma: allowlist secret
        "assistant_retrieval_k": 3,
        "assistant_vector_db_url": "postgresql+psycopg://x@127.0.0.1:1/x",
    }
    return Settings(**{**fields, **overrides})


class TestModelFactories:
    """The two models are different objects, each built once per process."""

    def test_the_answer_model_is_built_by_the_answer_factory_and_cached(self):
        """
        GIVEN the answer factory patched
        WHEN the answer model is requested twice
        THEN one model is built, by make_answer_model and not by make_chat_model
        """
        # GIVEN
        settings = _settings()
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_answer_model", return_value=MagicMock()) as make_answer,
            patch.object(deps, "make_chat_model", return_value=MagicMock()) as make_query,
        ):
            # WHEN
            first = deps.get_answer_model()
            second = deps.get_answer_model()

        # THEN
        assert first is second
        make_answer.assert_called_once_with(settings)
        make_query.assert_not_called()

    def test_the_query_model_is_built_by_the_chat_factory_and_cached(self):
        """
        GIVEN the chat factory patched
        WHEN the query model is requested twice
        THEN one model is built, by make_chat_model and not by make_answer_model
        """
        # GIVEN
        settings = _settings()
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_answer_model", return_value=MagicMock()) as make_answer,
            patch.object(deps, "make_chat_model", return_value=MagicMock()) as make_query,
        ):
            # WHEN
            first = deps.get_query_model()
            second = deps.get_query_model()

        # THEN
        assert first is second
        make_query.assert_called_once_with(settings)
        make_answer.assert_not_called()


class TestGetDocsRetriever:
    """The retriever searches with the query model and returns the configured number of passages."""

    @staticmethod
    def _build(settings: Settings) -> SimpleNamespace:
        query_model = MagicMock(name="query_model")
        answer_model = MagicMock(name="answer_model")
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "get_query_model", return_value=query_model),
            patch.object(deps, "get_answer_model", return_value=answer_model),
            patch.object(deps, "make_engine") as make_engine,
            patch.object(deps, "open_store") as open_store,
            patch.object(deps, "make_embeddings") as make_embeddings,
            patch.object(deps, "DocsRetriever") as retriever_cls,
        ):
            deps.get_docs_retriever()
        return SimpleNamespace(
            retriever_kwargs=retriever_cls.call_args.kwargs,
            query_model=query_model,
            answer_model=answer_model,
            make_engine=make_engine,
            open_store=open_store,
            make_embeddings=make_embeddings,
        )

    def test_the_retriever_gets_the_query_model_never_the_answer_model(self):
        """
        GIVEN the default retrieval config, which translates the query first
        WHEN the retriever is built
        THEN its model is the query model, and the answer model is not asked for at all
        """
        # WHEN
        built = self._build(_settings())

        # THEN
        assert built.retriever_kwargs["llm"] is built.query_model
        assert built.retriever_kwargs["llm"] is not built.answer_model

    def test_the_retriever_returns_the_configured_number_of_passages(self):
        """
        GIVEN assistant_retrieval_k set to 4
        WHEN the retriever is built
        THEN its config asks for 4 passages, and every other field keeps its default
        """
        # WHEN
        built = self._build(_settings(assistant_retrieval_k=4))

        # THEN
        assert built.retriever_kwargs["config"] == RetrievalConfig(k=4)

    def test_the_store_is_opened_on_the_configured_database_and_collection(self):
        """
        GIVEN settings naming a vector database and a collection
        WHEN the retriever is built
        THEN the engine is made from that URL and the store opened on that collection with
             the embeddings client
        """
        # GIVEN
        settings = _settings(assistant_collection="some_collection")

        # WHEN
        built = self._build(settings)

        # THEN
        built.make_engine.assert_called_once_with(settings.assistant_vector_db_url)
        built.open_store.assert_called_once_with(
            built.make_engine.return_value,
            "some_collection",
            built.make_embeddings.return_value,
        )
        assert built.retriever_kwargs["store"] is built.open_store.return_value

    def test_no_reranker_is_built_while_the_config_leaves_it_off(self):
        """
        GIVEN the default config, whose reranking is off
        WHEN the retriever is built
        THEN it is given no reranker
        """
        # WHEN
        built = self._build(_settings())

        # THEN
        assert built.retriever_kwargs["reranker"] is None

    def test_a_reranker_is_built_when_the_config_turns_it_on(self):
        """
        GIVEN a retrieval config with reranking on
        WHEN the retriever is built
        THEN it is given a reranker for the configured rerank server
        """
        # GIVEN
        settings = _settings()
        config = RetrievalConfig(k=3, rerank=True)
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "RetrievalConfig", return_value=config),
            patch.object(deps, "get_query_model", return_value=MagicMock()),
            patch.object(deps, "make_engine"),
            patch.object(deps, "open_store"),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "DocsRetriever") as retriever_cls,
            patch.object(deps, "LlamaServerReranker") as reranker_cls,
        ):
            # WHEN
            deps.get_docs_retriever()

        # THEN
        reranker_cls.assert_called_once_with(
            settings.assistant_rerank_base_url,
            settings.assistant_rerank_model,
            settings.assistant_llm_timeout_seconds,
        )
        assert retriever_cls.call_args.kwargs["reranker"] is reranker_cls.return_value

    def test_no_query_model_is_asked_for_when_the_config_never_transforms_queries(self):
        """
        GIVEN a retrieval config that leaves the query alone
        WHEN the retriever is built
        THEN it is given no model
        """
        # GIVEN
        settings = _settings()
        config = RetrievalConfig(k=3, query_transform="none")
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "RetrievalConfig", return_value=config),
            patch.object(deps, "get_query_model") as get_query_model,
            patch.object(deps, "make_engine"),
            patch.object(deps, "open_store"),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "DocsRetriever") as retriever_cls,
        ):
            # WHEN
            deps.get_docs_retriever()

        # THEN
        get_query_model.assert_not_called()
        assert retriever_cls.call_args.kwargs["llm"] is None

    def test_the_retriever_is_built_once_per_process(self):
        """
        GIVEN a retriever built through the factory
        WHEN the factory is called again
        THEN the same retriever comes back and the store is not opened again
        """
        # GIVEN
        settings = _settings()
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "get_query_model", return_value=MagicMock()),
            patch.object(deps, "make_engine"),
            patch.object(deps, "open_store") as open_store,
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "DocsRetriever", side_effect=lambda **_: MagicMock()),
        ):
            # WHEN
            first = deps.get_docs_retriever()
            second = deps.get_docs_retriever()

        # THEN
        assert first is second
        open_store.assert_called_once()


class TestClearCaches:
    """One helper drops every process-wide object the factories keep."""

    def test_every_cached_factory_builds_again_after_it(self):
        """
        GIVEN the two models and the retriever all built once
        WHEN the caches are cleared and the factories called again
        THEN each of them builds a new object
        """
        # GIVEN
        settings = _settings()
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_answer_model", side_effect=lambda _: MagicMock()),
            patch.object(deps, "make_chat_model", side_effect=lambda _: MagicMock()),
            patch.object(deps, "make_engine"),
            patch.object(deps, "open_store"),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "DocsRetriever", side_effect=lambda **_: MagicMock()),
        ):
            before = (deps.get_answer_model(), deps.get_query_model(), deps.get_docs_retriever())

            # WHEN
            deps.clear_caches()
            after = (deps.get_answer_model(), deps.get_query_model(), deps.get_docs_retriever())

        # THEN
        assert all(new is not old for new, old in zip(after, before, strict=True))


class TestBuildFailures:
    """A backend that is down while a process-wide object is built is unavailable, not a bug."""

    @pytest.fixture
    def records(self):
        with captured_log_records("api.assistant.deps") as captured:
            yield captured

    @pytest.mark.parametrize(
        "failure",
        [
            OperationalError("SELECT 1", {}, Exception("connection refused by secret-host")),
            ConnectionRefusedError("secret-host refused"),
            openai.APIConnectionError(request=httpx.Request("GET", "http://secret-host/")),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_the_retriever_being_built_against_a_down_backend_is_unavailable(
        self, failure, records
    ):
        """
        GIVEN a store that cannot be opened because its backend is down
        WHEN the retriever is requested
        THEN AssistantUnavailableError is raised and one warning records the event, the mode
             and the error class, never the error's text
        """
        # GIVEN
        settings = _settings()

        # WHEN
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_engine"),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", side_effect=failure),
            pytest.raises(AssistantUnavailableError),
        ):
            deps.get_docs_retriever()

        # THEN
        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.mode, record.reason) == (
            "assistant_dependency_unavailable",
            settings.assistant_mode,
            type(failure).__name__,
        )
        assert not any("secret-host" in str(value) for value in vars(record).values())

    def test_an_error_outside_the_list_still_surfaces_as_itself(self):
        """
        GIVEN a store that fails with a programming error while it is opened
        WHEN the retriever is requested
        THEN that error propagates and is not turned into unavailability
        """
        # WHEN/THEN
        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "make_engine"),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", side_effect=RuntimeError("bug")),
            pytest.raises(RuntimeError, match="bug"),
        ):
            deps.get_docs_retriever()

    def test_a_missing_vector_database_url_is_unavailable_and_names_the_setting(self, records):
        """
        GIVEN no ASSISTANT_VECTOR_DB_URL
        WHEN the retriever is requested
        THEN AssistantUnavailableError is raised without an engine being made, and one warning
             names the missing setting and nothing else
        """
        # GIVEN
        settings = _settings(assistant_vector_db_url="")

        # WHEN
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_engine") as make_engine,
            pytest.raises(AssistantUnavailableError),
        ):
            deps.get_docs_retriever()

        # THEN
        make_engine.assert_not_called()
        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.setting) == (
            "assistant_setting_missing",
            "ASSISTANT_VECTOR_DB_URL",
        )

    def test_a_failed_build_is_not_cached(self):
        """
        GIVEN a retriever that failed to build because the database was down
        WHEN the database is back and the retriever is requested again, without clearing
             any cache
        THEN it is built, so one outage does not outlive the database's recovery
        """
        # GIVEN
        settings = _settings()
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "get_query_model", return_value=MagicMock()),
            patch.object(deps, "make_engine"),
            patch.object(deps, "make_embeddings"),
            patch.object(
                deps, "open_store", side_effect=[ConnectionRefusedError("down"), MagicMock()]
            ),
            patch.object(deps, "DocsRetriever", side_effect=lambda **_: MagicMock()),
        ):
            with pytest.raises(AssistantUnavailableError):
                deps.get_docs_retriever()

            # WHEN
            retriever = deps.get_docs_retriever()

        # THEN
        assert retriever is not None
