"""Tests for the assistant's dependency factories (fakes only, no network)."""

import logging
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx
import openai
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from api.assistant import deps
from api.assistant.agent.context import AssistantContext
from api.assistant.errors import AssistantRateLimitedError, AssistantUnavailableError
from api.assistant.rag.retrieval import RetrievalConfig
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


class TestEnforceMessageLimit:
    """The hourly cap is spent through the throttle, off the event loop."""

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
        await deps.enforce_message_limit(user, throttle)

        # THEN
        throttle.hit.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_a_spent_budget_raises_the_rate_limited_error(self):
        """
        GIVEN a throttle that refuses the message
        WHEN the limit dependency runs
        THEN AssistantRateLimitedError is raised
        """
        # GIVEN
        throttle = MagicMock()
        throttle.hit.return_value = False

        # WHEN/THEN
        with pytest.raises(AssistantRateLimitedError):
            await deps.enforce_message_limit(MagicMock(id=uuid4()), throttle)

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
        await deps.enforce_message_limit(MagicMock(id=uuid4()), _Throttle())

        # THEN
        assert threads
        assert threads[0] != threading.get_ident()


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
