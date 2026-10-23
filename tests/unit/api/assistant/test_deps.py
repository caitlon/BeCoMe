"""Tests for the assistant's dependency factories (fakes only, no network)."""

import logging
import threading
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import openai
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from api.assistant import deps, rate_limit
from api.assistant.agent.context import AssistantContext
from api.assistant.errors import (
    AssistantBusyError,
    AssistantRateLimitedError,
    AssistantUnavailableError,
)
from api.assistant.rag.models import make_answer_model, make_chat_model
from api.assistant.rag.retrieval import RetrievalConfig
from api.assistant.rag.store import CollectionUnavailableError
from api.assistant.rate_limit import (
    GLOBAL_KEY,
    get_assistant_global_throttle,
    get_assistant_throttle,
)
from api.config import Settings
from api.exceptions import ValidationError
from api.schemas.assistant import AssistantChatRequest
from tests.shared.helpers import captured_log_records

PROJECT_ID = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"


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


def _engine() -> MagicMock:
    """Stand in for a PGEngine whose close is awaitable."""
    return MagicMock(name="engine", close=AsyncMock())


def _request(client_host: str = "203.0.113.5") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/assistant/chat",
        "headers": [],
        "app": FastAPI(),
        "client": (client_host, 12345),
    }
    return Request(scope)


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
        THEN the engine is made from that URL, capped at 30 seconds a statement, and the
             store opened on that collection with the embeddings client
        """
        # GIVEN
        settings = _settings(assistant_collection="some_collection")

        # WHEN
        built = self._build(settings)

        # THEN
        built.make_engine.assert_called_once_with(
            settings.assistant_vector_db_url, statement_timeout_ms=30000
        )
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


def _chat_model() -> MagicMock:
    """Stand in for a ChatOpenAI whose two root clients close."""
    return MagicMock(name="chat_model", root_async_client=AsyncMock(), root_client=MagicMock())


class TestCloseAssistantResources:
    """Shutdown closes what was built, builds nothing, and one failure stops nobody."""

    @staticmethod
    def _build_everything(
        engine: MagicMock, answer: MagicMock, query: MagicMock
    ) -> tuple[MagicMock, MagicMock]:
        """Build the models, the retriever and both Redis-backed throttles.

        :return: The Redis clients of the per-user throttle and of the global one.
        """
        user_client = MagicMock(name="user_redis_client")
        global_client = MagicMock(name="global_redis_client")
        settings = _settings(redis_url="redis://cache:6379/0")
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_answer_model", return_value=answer),
            patch.object(deps, "make_chat_model", return_value=query),
            patch.object(deps, "make_engine", return_value=engine),
            patch.object(deps, "open_store"),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "DocsRetriever", side_effect=lambda **_: MagicMock()),
            patch.object(rate_limit, "get_settings", return_value=settings),
            patch.object(rate_limit.redis, "from_url", side_effect=[user_client, global_client]),
        ):
            deps.get_answer_model()
            deps.get_query_model()
            deps.get_docs_retriever()
            get_assistant_throttle()
            get_assistant_global_throttle()
        return user_client, global_client

    @pytest.fixture(autouse=True)
    def _fresh_throttles(self):
        get_assistant_throttle.cache_clear()
        get_assistant_global_throttle.cache_clear()
        yield
        get_assistant_throttle.cache_clear()
        get_assistant_global_throttle.cache_clear()

    @pytest.mark.asyncio
    async def test_it_closes_every_resource_that_was_built(self):
        """
        GIVEN both models, the retriever and both throttles built
        WHEN the resources are closed
        THEN the engine, each model's two clients and each throttle's Redis client are closed,
             and the caches are empty afterwards
        """
        # GIVEN
        engine, answer, query = _engine(), _chat_model(), _chat_model()
        user_client, global_client = self._build_everything(engine, answer, query)

        # WHEN
        await deps.close_assistant_resources()

        # THEN
        engine.close.assert_awaited_once()
        for model in (answer, query):
            model.root_async_client.close.assert_awaited_once()
            model.root_client.close.assert_called_once_with()
        user_client.close.assert_called_once_with()
        global_client.close.assert_called_once_with()
        assert deps.get_answer_model.cache_info().currsize == 0
        assert get_assistant_throttle.cache_info().currsize == 0
        assert get_assistant_global_throttle.cache_info().currsize == 0
        assert deps._docs_resources is None

    @pytest.mark.parametrize("factory", [make_chat_model, make_answer_model])
    def test_the_real_chat_models_expose_the_clients_that_shutdown_closes(self, factory):
        """
        GIVEN a chat model built by the real factory, which makes no network call
        WHEN its two root clients are looked up by the names shutdown uses
        THEN both exist and can be closed, so a renamed attribute in a later langchain-openai
             fails here and does not leak silently
        """
        # WHEN
        model = factory(_settings())

        # THEN
        for attribute in ("root_async_client", "root_client"):
            assert callable(getattr(getattr(model, attribute, None), "close", None)), attribute

    @pytest.mark.asyncio
    async def test_it_builds_nothing_that_was_never_built(self):
        """
        GIVEN a process that built none of the resources
        WHEN the resources are closed
        THEN no model, engine or Redis client is made
        """
        # WHEN
        with (
            patch.object(deps, "make_answer_model") as make_answer,
            patch.object(deps, "make_chat_model") as make_chat,
            patch.object(deps, "make_engine") as make_engine,
            patch.object(rate_limit.redis, "from_url") as from_url,
        ):
            await deps.close_assistant_resources()

        # THEN
        for factory in (make_answer, make_chat, make_engine, from_url):
            factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_failing_close_is_logged_and_the_rest_still_close(self):
        """
        GIVEN resources built, an engine whose close fails and an answer model whose async
            client fails
        WHEN the resources are closed
        THEN every other resource is still closed, and each failure leaves one warning with the
             resource and the error class only, never the error's text
        """
        # GIVEN
        engine, answer, query = _engine(), _chat_model(), _chat_model()
        engine.close.side_effect = ConnectionError("down at secret-host")
        answer.root_async_client.close.side_effect = RuntimeError("secret-host")
        user_client, global_client = self._build_everything(engine, answer, query)

        # WHEN
        with captured_log_records("api.assistant.deps") as records:
            await deps.close_assistant_resources()

        # THEN
        assert [(r.event, r.resource, r.reason) for r in records] == [
            ("assistant_shutdown_close_failed", "docs_engine", "ConnectionError"),
            ("assistant_shutdown_close_failed", "answer_model_async_client", "RuntimeError"),
        ]
        assert not any(
            "secret-host" in str(value) for record in records for value in vars(record).values()
        )
        answer.root_client.close.assert_called_once_with()
        query.root_async_client.close.assert_awaited_once()
        query.root_client.close.assert_called_once_with()
        user_client.close.assert_called_once_with()
        global_client.close.assert_called_once_with()


class TestGetAssistantService:
    """The service is built per request from the settings and the answer model."""

    def test_wires_the_settings_and_the_answer_model(self):
        """
        GIVEN settings and an answer model
        WHEN the service dependency is called
        THEN AssistantService is built from exactly those two
        """
        # GIVEN
        settings = _settings()
        answer_model = MagicMock()

        # WHEN
        with patch.object(deps, "AssistantService") as service_cls:
            service = deps.get_assistant_service(settings, answer_model)

        # THEN
        service_cls.assert_called_once_with(settings, answer_model)
        assert service is service_cls.return_value


def _open_ceiling() -> MagicMock:
    """Return a global throttle that allows every message."""
    ceiling = MagicMock()
    ceiling.hit_key.return_value = True
    return ceiling


class TestEnforceMessageLimit:
    """The hourly caps are spent through the throttles, off the event loop."""

    @pytest.mark.asyncio
    async def test_a_message_within_budget_passes(self):
        """
        GIVEN a throttle that allows the message
        WHEN the limit dependency runs
        THEN it returns and the throttle was asked about that user
        """
        # GIVEN
        throttle = MagicMock()
        throttle.hit.return_value = True
        user = MagicMock(id=uuid4())

        # WHEN
        await deps.enforce_message_limit(user, throttle, _open_ceiling())

        # THEN
        throttle.hit.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_a_spent_budget_raises_the_rate_limited_error(self):
        """
        GIVEN a throttle that refuses the message
        WHEN the limit dependency runs
        THEN AssistantRateLimitedError is raised carrying the seconds the throttle reports
        """
        # GIVEN
        throttle = MagicMock()
        throttle.hit.return_value = False
        throttle.retry_after.return_value = 1234
        user = MagicMock(id=uuid4())

        # WHEN/THEN
        with pytest.raises(AssistantRateLimitedError) as caught:
            await deps.enforce_message_limit(user, throttle, _open_ceiling())
        assert caught.value.retry_after == 1234
        throttle.retry_after.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_the_throttle_runs_in_a_worker_thread(self):
        """
        GIVEN a throttle that records the thread it is called on
        WHEN the limit dependency runs on the event loop
        THEN the throttle was called on another thread, so a Redis round trip cannot
             stall every other request
        """
        # GIVEN
        threads: list[int] = []

        class _Throttle:
            def hit(self, user_id: UUID) -> bool:
                threads.append(threading.get_ident())
                return True

        # WHEN
        await deps.enforce_message_limit(MagicMock(id=uuid4()), _Throttle(), _open_ceiling())

        # THEN
        assert threads
        assert threads[0] != threading.get_ident()

    @pytest.mark.asyncio
    async def test_retry_after_runs_in_a_worker_thread(self):
        """
        GIVEN a refusing throttle that records the thread retry_after is called on
        WHEN the limit dependency runs on the event loop
        THEN retry_after ran on another thread, so a Redis round trip cannot stall the loop
        """
        # GIVEN
        threads: list[int] = []

        class _Throttle:
            def hit(self, user_id: UUID) -> bool:
                return False

            def retry_after(self, user_id: UUID) -> int:
                threads.append(threading.get_ident())
                return 5

        # WHEN
        with pytest.raises(AssistantRateLimitedError):
            await deps.enforce_message_limit(MagicMock(id=uuid4()), _Throttle(), _open_ceiling())

        # THEN
        assert threads
        assert threads[0] != threading.get_ident()

    @pytest.mark.asyncio
    async def test_the_global_ceiling_is_spent_under_its_own_key_after_the_users_budget(self):
        """
        GIVEN a user within budget and a global throttle that allows the message
        WHEN the limit dependency runs
        THEN the user's budget was hit once and the ceiling once, under the global key
        """
        # GIVEN
        throttle = MagicMock()
        throttle.hit.return_value = True
        ceiling = _open_ceiling()
        user = MagicMock(id=uuid4())

        # WHEN
        await deps.enforce_message_limit(user, throttle, ceiling)

        # THEN
        throttle.hit.assert_called_once_with(user.id)
        ceiling.hit_key.assert_called_once_with(GLOBAL_KEY)

    @pytest.mark.asyncio
    async def test_a_spent_user_budget_leaves_the_global_ceiling_untouched(self):
        """
        GIVEN a user whose own budget is spent
        WHEN the limit dependency runs
        THEN the 429 is raised and the global ceiling was never hit, so an account with a
             spent budget cannot drain the shared one
        """
        # GIVEN
        throttle = MagicMock()
        throttle.hit.return_value = False
        throttle.retry_after.return_value = 60
        ceiling = _open_ceiling()

        # WHEN/THEN
        with pytest.raises(AssistantRateLimitedError):
            await deps.enforce_message_limit(MagicMock(id=uuid4()), throttle, ceiling)
        assert ceiling.mock_calls == []

    @pytest.mark.asyncio
    async def test_a_reached_ceiling_raises_busy_with_the_seconds_until_its_window_closes(self):
        """
        GIVEN a user within budget and a global ceiling that is reached
        WHEN the limit dependency runs
        THEN AssistantBusyError is raised for the global reason, carrying the seconds the
             ceiling reports under the global key
        """
        # GIVEN
        throttle = MagicMock()
        throttle.hit.return_value = True
        ceiling = MagicMock()
        ceiling.hit_key.return_value = False
        ceiling.retry_after_key.return_value = 1800

        # WHEN/THEN
        with pytest.raises(AssistantBusyError) as caught:
            await deps.enforce_message_limit(MagicMock(id=uuid4()), throttle, ceiling)
        assert caught.value.reason == "global"
        assert caught.value.retry_after == 1800
        ceiling.retry_after_key.assert_called_once_with(GLOBAL_KEY)

    @pytest.mark.asyncio
    async def test_the_ceiling_runs_in_a_worker_thread(self):
        """
        GIVEN a refusing global throttle that records the threads it is called on
        WHEN the limit dependency runs on the event loop
        THEN hit_key and retry_after_key both ran on another thread
        """
        # GIVEN
        threads: list[int] = []

        class _Ceiling:
            def hit_key(self, key: str) -> bool:
                threads.append(threading.get_ident())
                return False

            def retry_after_key(self, key: str) -> int:
                threads.append(threading.get_ident())
                return 5

        # WHEN
        with pytest.raises(AssistantBusyError):
            await deps.enforce_message_limit(
                MagicMock(id=uuid4()), MagicMock(hit=MagicMock(return_value=True)), _Ceiling()
            )

        # THEN
        assert len(threads) == 2
        assert threading.get_ident() not in threads


class TestTurnSlots:
    """The slot table counts turns in the process and per user, and never waits."""

    def test_turns_within_both_caps_are_admitted(self):
        """
        GIVEN a table of three slots with two allowed per user
        WHEN two users take a slot each
        THEN both are admitted
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=3, max_per_user=2)

        # WHEN/THEN
        assert slots.acquire(uuid4()) is None
        assert slots.acquire(uuid4()) is None

    def test_a_full_process_refuses_whoever_asks(self):
        """
        GIVEN a table of two slots, both taken by different users
        WHEN a third user asks
        THEN the refusal names the process cap
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=2, max_per_user=2)
        slots.acquire(uuid4())
        slots.acquire(uuid4())

        # WHEN/THEN
        assert slots.acquire(uuid4()) == "process"

    def test_one_user_cannot_hold_more_than_their_share_while_others_get_in(self):
        """
        GIVEN a table of four slots with two allowed per user, and one user holding two
        WHEN that user asks again, then another user asks
        THEN the first is refused with the user cap and the second is admitted
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=4, max_per_user=2)
        greedy = uuid4()
        slots.acquire(greedy)
        slots.acquire(greedy)

        # WHEN/THEN
        assert slots.acquire(greedy) == "user"
        assert slots.acquire(uuid4()) is None

    def test_a_refusal_takes_nothing(self):
        """
        GIVEN a table of one slot that is taken
        WHEN a refused turn asks and the holder then releases
        THEN the slot is free again, so the refusal had not counted
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=1, max_per_user=1)
        holder = uuid4()
        slots.acquire(holder)
        assert slots.acquire(uuid4()) == "process"

        # WHEN
        slots.release(holder)

        # THEN
        assert slots.acquire(uuid4()) is None

    def test_release_frees_the_process_slot_and_the_users_share(self):
        """
        GIVEN a user who reached their cap of one
        WHEN they release and ask again
        THEN they are admitted
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=5, max_per_user=1)
        user = uuid4()
        slots.acquire(user)
        assert slots.acquire(user) == "user"

        # WHEN
        slots.release(user)

        # THEN
        assert slots.acquire(user) is None

    def test_a_users_entry_is_dropped_when_it_reaches_zero(self):
        """
        GIVEN two users holding one slot each
        WHEN both release
        THEN the table keeps no entry for either, so it does not grow with the users it has seen
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=5, max_per_user=2)
        first, second = uuid4(), uuid4()
        slots.acquire(first)
        slots.acquire(second)

        # WHEN
        slots.release(first)
        slots.release(second)

        # THEN
        assert slots.holders == {}

    def test_releasing_a_slot_never_taken_changes_nothing(self):
        """
        GIVEN a table of two slots with one held by another user
        WHEN a user who holds none releases
        THEN nothing is raised, no entry appears, and the process still has exactly one slot
             free, so the total was not corrupted
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=2, max_per_user=2)
        holder = uuid4()
        slots.acquire(holder)

        # WHEN
        slots.release(uuid4())

        # THEN
        assert slots.holders == {holder: 1}
        assert slots.acquire(uuid4()) is None
        assert slots.acquire(uuid4()) == "process"

    def test_it_is_sized_from_settings_and_rebuilt_after_clear_caches(self):
        """
        GIVEN a cap of three turns in the settings
        WHEN the cached table is asked for twice, and again after clear_caches
        THEN the first two are the same object sized from the settings, and the third is new
        """
        # GIVEN
        settings = _settings(assistant_max_concurrent_turns=3)
        with patch.object(deps, "get_settings", return_value=settings):
            # WHEN
            first = deps.get_turn_slots()
            second = deps.get_turn_slots()
            deps.clear_caches()
            third = deps.get_turn_slots()

        # THEN
        assert first is second
        assert first.max_total == 3
        assert first.max_per_user == deps.MAX_TURNS_PER_USER
        assert third is not first


class TestHoldTurnSlot:
    """The dependency holds a slot for the turn and refuses at once when none is free."""

    @pytest.fixture
    def records(self):
        with captured_log_records("api.assistant.deps") as captured:
            yield captured

    @pytest.mark.asyncio
    async def test_the_slot_is_held_inside_and_released_after_a_normal_exit(self):
        """
        GIVEN a table of one slot
        WHEN the dependency runs and the response completes
        THEN the slot was taken while it ran, and is free after
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=1, max_per_user=1)
        user = MagicMock(id=uuid4())

        # WHEN
        async with asynccontextmanager(deps.hold_turn_slot)(user, slots):
            held = slots.acquire(uuid4())

        # THEN
        assert held == "process"
        assert slots.acquire(uuid4()) is None

    @pytest.mark.asyncio
    async def test_the_slot_is_released_when_the_turn_raises(self):
        """
        GIVEN a table of one slot
        WHEN the turn raises inside the dependency
        THEN the error goes on and the slot is free again
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=1, max_per_user=1)
        user = MagicMock(id=uuid4())

        # WHEN
        with pytest.raises(RuntimeError, match="turn failed"):
            async with asynccontextmanager(deps.hold_turn_slot)(user, slots):
                raise RuntimeError("turn failed")

        # THEN
        assert slots.holders == {}
        assert slots.acquire(uuid4()) is None

    @pytest.mark.asyncio
    async def test_a_full_process_is_refused_with_the_wait_and_the_reason_and_no_record(
        self, records
    ):
        """
        GIVEN a table of one slot that another user holds
        WHEN the dependency runs
        THEN AssistantBusyError carries the retry wait and the process reason, the holder's slot
             is untouched, and the dependency writes no record: the handler writes the one
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=1, max_per_user=1)
        holder = uuid4()
        slots.acquire(holder)
        user = MagicMock(id=uuid4())

        # WHEN
        with pytest.raises(AssistantBusyError) as caught:
            async with asynccontextmanager(deps.hold_turn_slot)(user, slots):
                pytest.fail("a refused turn must not run")

        # THEN
        assert caught.value.retry_after == deps.TURN_SLOT_RETRY_SECONDS == 5
        assert caught.value.reason == "process"
        assert slots.holders == {holder: 1}
        assert records == []

    @pytest.mark.asyncio
    async def test_a_user_at_their_share_is_refused_while_the_process_has_room(self):
        """
        GIVEN a table of ten slots and a user already holding their two
        WHEN the dependency runs for that user, and then for another
        THEN the first is refused with the user reason, and the second runs
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=10, max_per_user=2)
        greedy = MagicMock(id=uuid4())
        slots.acquire(greedy.id)
        slots.acquire(greedy.id)

        # WHEN/THEN
        with pytest.raises(AssistantBusyError) as caught:
            async with asynccontextmanager(deps.hold_turn_slot)(greedy, slots):
                pytest.fail("a refused turn must not run")
        async with asynccontextmanager(deps.hold_turn_slot)(MagicMock(id=uuid4()), slots):
            pass
        assert caught.value.reason == "user"


class _FakeClient:
    """Stands in for UserApiClient: records how it was built and whether it was closed."""

    instances: ClassVar[list["_FakeClient"]] = []

    def __init__(self, app: Any, access_token: str, client_ip: str) -> None:
        self.app = app
        self.access_token = access_token
        self.client_ip = client_ip
        self.closed = 0
        _FakeClient.instances.append(self)

    async def aclose(self) -> None:
        self.closed += 1


@pytest.fixture
def fake_client():
    """Replace UserApiClient in the deps module with a recording fake."""
    _FakeClient.instances = []
    with patch.object(deps, "UserApiClient", _FakeClient):
        yield _FakeClient


class TestOpenChatTurn:
    """The client and the context are built for one request and the client is always closed."""

    @staticmethod
    def _open(data: AssistantChatRequest, request: Request, retriever: Any):
        return asynccontextmanager(deps.open_chat_turn)(request, data, "token-abc", retriever)

    @pytest.mark.asyncio
    async def test_builds_a_client_for_this_caller_and_a_context_around_it(self, fake_client):
        """
        GIVEN a request naming a project and a locale
        WHEN the turn is opened
        THEN the client carries the caller's token and address, and the context holds
             that client, the given retriever, the project id as a string and the locale
        """
        # GIVEN
        request = _request("203.0.113.5")
        retriever = MagicMock()
        data = AssistantChatRequest(message="hi", project_id=UUID(PROJECT_ID), locale="cs")

        # WHEN
        async with self._open(data, request, retriever) as turn:
            # THEN
            assert turn.request is data
            ctx = turn.context
            assert isinstance(ctx, AssistantContext)
            (client,) = fake_client.instances
            assert client.app is request.app
            assert client.access_token == "token-abc"
            assert client.client_ip == "203.0.113.5"
            assert ctx.client is client
            assert ctx.retriever is retriever
            assert ctx.current_project_id == PROJECT_ID
            assert isinstance(ctx.current_project_id, str)
            assert ctx.locale == "cs"
            assert ctx.tool_outputs == []

    @pytest.mark.asyncio
    async def test_a_request_without_a_project_has_no_current_project(self, fake_client):
        """
        GIVEN a request that names no project
        WHEN the turn is opened
        THEN the context has no current project
        """
        # WHEN
        async with self._open(AssistantChatRequest(message="hi"), _request(), MagicMock()) as turn:
            # THEN
            assert turn.context.current_project_id is None

    @pytest.mark.asyncio
    async def test_closes_the_client_when_the_turn_ends(self, fake_client):
        """
        GIVEN an opened turn
        WHEN the block ends normally
        THEN the client was closed exactly once
        """
        # WHEN
        async with self._open(AssistantChatRequest(message="hi"), _request(), MagicMock()):
            (client,) = fake_client.instances
            assert client.closed == 0

        # THEN
        assert client.closed == 1

    @pytest.mark.asyncio
    async def test_closes_the_client_when_the_turn_fails(self, fake_client):
        """
        GIVEN an opened turn
        WHEN the block raises
        THEN the client was still closed exactly once and the error propagates
        """
        # WHEN
        with pytest.raises(RuntimeError, match="boom"):
            async with self._open(AssistantChatRequest(message="hi"), _request(), MagicMock()):
                raise RuntimeError("boom")

        # THEN
        (client,) = fake_client.instances
        assert client.closed == 1

    @pytest.mark.asyncio
    async def test_each_turn_gets_its_own_client_and_source_registry(self, fake_client):
        """
        GIVEN two turns opened one after the other
        WHEN their contexts are compared
        THEN neither the client nor the source registry is shared, so one caller's token
             never reaches another caller's request
        """
        # WHEN
        async with self._open(AssistantChatRequest(message="a"), _request(), MagicMock()) as one:
            pass
        async with self._open(AssistantChatRequest(message="b"), _request(), MagicMock()) as two:
            pass

        # THEN
        assert one.context.client is not two.context.client
        assert one.context.sources is not two.context.sources
        assert one.context.tool_outputs is not two.context.tool_outputs


class TestMessageLength:
    """A message longer than assistant_max_message_chars is refused before anything is built."""

    def test_a_message_of_the_configured_length_passes(self):
        """
        GIVEN a limit of ten characters
        WHEN a message of exactly ten is checked
        THEN the same request comes back
        """
        # GIVEN
        data = AssistantChatRequest(message="x" * 10)

        # WHEN
        checked = deps.get_chat_request(data, _settings(assistant_max_message_chars=10))

        # THEN
        assert checked is data

    def test_one_character_more_is_refused_without_echoing_the_text(self):
        """
        GIVEN a limit of ten characters
        WHEN a message of eleven is checked
        THEN the domain ValidationError is raised, naming the limit and not the text
        """
        # GIVEN
        data = AssistantChatRequest(message="secret text")

        # WHEN/THEN
        with pytest.raises(ValidationError, match="10") as raised:
            deps.get_chat_request(data, _settings(assistant_max_message_chars=10))
        assert "secret text" not in str(raised.value)

    def test_the_default_limit_lets_the_schema_ceiling_through(self):
        """
        GIVEN the default settings
        WHEN a message of 4000 characters, the schema's own ceiling, is checked
        THEN it passes
        """
        # GIVEN
        data = AssistantChatRequest(message="x" * 4000)

        # WHEN/THEN
        assert deps.get_chat_request(data, _settings()) is data


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
            CollectionUnavailableError("collection 'secret_table' cannot be opened"),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_the_retriever_being_built_against_a_down_backend_is_unavailable(
        self, failure, records
    ):
        """
        GIVEN a store that cannot be opened because its backend is down
        WHEN the retriever is requested
        THEN AssistantUnavailableError is raised, the engine's pool is closed, and one
             warning records the event, the mode and the error class, never the error's text
        """
        # GIVEN
        settings = _settings()
        engine = _engine()

        # WHEN
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "make_engine", return_value=engine),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", side_effect=failure),
            pytest.raises(AssistantUnavailableError),
        ):
            deps.get_docs_retriever()

        # THEN
        engine.close.assert_awaited_once()
        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.mode, record.reason) == (
            "assistant_dependency_unavailable",
            settings.assistant_mode,
            type(failure).__name__,
        )
        assert not any(
            "secret-host" in str(value) or "secret_table" in str(value)
            for value in vars(record).values()
        )

    def test_an_error_outside_the_list_still_surfaces_as_itself(self):
        """
        GIVEN a store that fails with a programming error while it is opened
        WHEN the retriever is requested
        THEN that error propagates and is not turned into unavailability
        """
        # WHEN/THEN
        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "make_engine", return_value=_engine()),
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
        THEN it is built on a fresh engine, and the failed attempt's engine was closed
        """
        # GIVEN
        settings = _settings()
        first, second = _engine(), _engine()
        with (
            patch.object(deps, "get_settings", return_value=settings),
            patch.object(deps, "get_query_model", return_value=MagicMock()),
            patch.object(deps, "make_engine", side_effect=[first, second]),
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
        first.close.assert_awaited_once()
        second.close.assert_not_awaited()

    def test_a_failure_after_the_store_opened_still_closes_the_engine(self):
        """
        GIVEN a store that opened, and a retriever that fails to build after it
        WHEN the retriever is requested
        THEN the engine is closed and the error goes on, unchanged
        """
        # GIVEN
        engine = _engine()
        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "get_query_model", return_value=MagicMock()),
            patch.object(deps, "make_engine", return_value=engine),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", return_value=MagicMock()),
            patch.object(deps, "DocsRetriever", side_effect=RuntimeError("bad config")),
            # WHEN/THEN
            pytest.raises(RuntimeError, match="bad config"),
        ):
            deps.get_docs_retriever()

        engine.close.assert_awaited_once()

    def test_a_failing_close_does_not_replace_the_original_error(self):
        """
        GIVEN a database that is down and an engine whose close fails too
        WHEN the retriever is requested
        THEN the outage is what is reported, not the failure to close
        """
        # GIVEN
        engine = _engine()
        engine.close.side_effect = RuntimeError("close failed")
        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "make_engine", return_value=engine),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", side_effect=ConnectionRefusedError("down")),
            # WHEN/THEN
            pytest.raises(AssistantUnavailableError),
        ):
            deps.get_docs_retriever()

        engine.close.assert_awaited_once()

    def test_a_failing_close_is_logged_and_the_original_error_still_propagates(self, records):
        """
        GIVEN a store that fails to open with a programming error and an engine whose close fails
        WHEN the retriever is requested
        THEN the programming error is what propagates, and one warning records the failed close
             with the error class only, never its text
        """
        # GIVEN
        engine = _engine()
        engine.close.side_effect = ConnectionError("close failed at secret-host")

        # WHEN
        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "make_engine", return_value=engine),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", side_effect=RuntimeError("bug")),
            pytest.raises(RuntimeError, match="bug"),
        ):
            deps.get_docs_retriever()

        # THEN
        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.reason) == ("assistant_engine_close_failed", "ConnectionError")
        assert not any("secret-host" in str(value) for value in vars(record).values())

    def test_concurrent_cold_requests_publish_one_retriever_and_close_the_rest(self):
        """
        GIVEN a slow engine build and several threads asking for the retriever at once
        WHEN they all start together on a cold process
        THEN every thread gets the same retriever, the engine published with it stays open,
             and every other engine that was built is closed
        """
        # GIVEN
        threads_count = 4
        start = threading.Barrier(threads_count, timeout=10)
        engines: list[MagicMock] = []
        results: list[Any] = []

        def _slow_engine(*args: Any, **kwargs: Any) -> MagicMock:
            time.sleep(0.05)
            engine = _engine()
            engines.append(engine)
            return engine

        def _ask() -> None:
            start.wait()
            results.append(deps.get_docs_retriever())

        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "get_query_model", return_value=MagicMock()),
            patch.object(deps, "make_engine", side_effect=_slow_engine),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", return_value=MagicMock()),
            patch.object(deps, "DocsRetriever", side_effect=lambda **_: MagicMock()),
        ):
            # WHEN
            workers = [threading.Thread(target=_ask) for _ in range(threads_count)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)

        # THEN
        assert not any(worker.is_alive() for worker in workers)
        assert len(results) == threads_count
        assert all(result is results[0] for result in results)
        assert deps._docs_resources is not None
        published = deps._docs_resources[1]
        assert published in engines
        published.close.assert_not_awaited()
        for engine in engines:
            if engine is not published:
                engine.close.assert_awaited_once()

    def test_a_losing_engine_that_fails_to_close_is_logged(self, records):
        """
        GIVEN a retriever already published by another thread, and a build that finishes after
            it, on an engine whose close fails
        WHEN the late build is published
        THEN the published retriever is returned, and one warning records the failed close
        """
        # GIVEN
        winner = (MagicMock(name="published"), _engine())
        loser_engine = _engine()
        loser_engine.close.side_effect = ConnectionError("close failed at secret-host")

        def _late_build() -> tuple[Any, Any]:
            deps._docs_resources = winner
            return MagicMock(name="late"), loser_engine

        # WHEN
        with patch.object(deps, "_build_docs_retriever", side_effect=_late_build):
            retriever = deps.get_docs_retriever()

        # THEN
        assert retriever is winner[0]
        winner[1].close.assert_not_awaited()
        (record,) = records
        assert (record.event, record.reason) == ("assistant_engine_close_failed", "ConnectionError")

    def test_failing_builds_are_not_serialised(self):
        """
        GIVEN the vector database down, and two threads that each need the other's build to
            overlap with its own to finish
        WHEN both ask for the retriever at once
        THEN both fail with the outage, so neither waited for the other's build to end
        """
        # GIVEN
        overlap = threading.Barrier(2, timeout=10)
        outcomes: list[str] = []

        def _store_down(*args: Any, **kwargs: Any) -> None:
            overlap.wait()
            raise ConnectionRefusedError("down")

        def _ask() -> None:
            try:
                deps.get_docs_retriever()
            except AssistantUnavailableError:
                outcomes.append("unavailable")
            except Exception as exc:
                outcomes.append(type(exc).__name__)

        with (
            patch.object(deps, "get_settings", return_value=_settings()),
            patch.object(deps, "make_engine", side_effect=lambda *a, **k: _engine()),
            patch.object(deps, "make_embeddings"),
            patch.object(deps, "open_store", side_effect=_store_down),
        ):
            # WHEN
            workers = [threading.Thread(target=_ask) for _ in range(2)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=10)

        # THEN
        assert not any(worker.is_alive() for worker in workers)
        assert outcomes == ["unavailable", "unavailable"]
        assert deps._docs_resources is None


def _mini_app() -> tuple[FastAPI, list[Any]]:
    """Build an app whose one route takes the turn dependency and reports what it saw."""
    app = FastAPI()
    opened: list[Any] = []

    def _counting_retriever() -> Any:
        return MagicMock()

    app.dependency_overrides[deps.get_docs_retriever] = _counting_retriever

    @app.post("/turn")
    async def turn_route(turn: deps.PreparedTurnDep) -> dict[str, Any]:
        opened.append(turn)
        return {"message": turn.request.message, "project": turn.context.current_project_id}

    return app, opened


class TestPreparedTurnThroughFastAPI:
    """The body is read and validated once, and the route sees what the dependency built."""

    def test_the_body_is_validated_once_and_reaches_route_and_context(self, fake_client):
        """
        GIVEN a route that takes the turn dependency
        WHEN a valid body is posted with a bearer token
        THEN the client was built once with that token, and the route's request and the
             context's project come from the same body
        """
        # GIVEN
        app, opened = _mini_app()

        # WHEN
        response = TestClient(app).post(
            "/turn",
            json={"message": "hi", "project_id": PROJECT_ID},
            headers={"Authorization": "Bearer token-xyz"},
        )

        # THEN
        assert response.status_code == 200
        assert response.json()["message"] == "hi"
        assert response.json()["project"] == PROJECT_ID
        assert len(opened) == 1
        (client,) = fake_client.instances
        assert client.access_token == "token-xyz"  # pragma: allowlist secret
        assert client.closed == 1

    def test_an_invalid_body_is_refused_once_and_builds_no_client(self, fake_client):
        """
        GIVEN a route that takes the turn dependency
        WHEN a body with an unknown field is posted
        THEN the answer is one 422 error for that field, and no client was built
        """
        # GIVEN
        app, opened = _mini_app()

        # WHEN
        response = TestClient(app).post(
            "/turn",
            json={"message": "hi", "unknown": 1},
            headers={"Authorization": "Bearer token-xyz"},
        )

        # THEN
        assert response.status_code == 422
        assert [error["loc"] for error in response.json()["detail"]] == [["body", "unknown"]]
        assert opened == []
        assert fake_client.instances == []

    def test_a_request_without_a_token_builds_no_client(self, fake_client):
        """
        GIVEN a route that takes the turn dependency
        WHEN a valid body is posted with neither a cookie nor a bearer token
        THEN the answer is 401 and no client was built
        """
        # GIVEN
        app, _ = _mini_app()

        # WHEN
        response = TestClient(app).post("/turn", json={"message": "hi"})

        # THEN
        assert response.status_code == 401
        assert fake_client.instances == []
