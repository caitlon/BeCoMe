"""Dependency factories for the assistant's chat route.

Kept out of ``api/dependencies.py`` on purpose: that module loads in every deployed
process, and nothing there may import langchain or openai. This one is imported only by
code that loads when ``settings.assistant_enabled`` is true.

What lives for the whole process is cached here: the two chat models and the
documentation retriever, which owns a BM25 index and the vector store's engine.
:func:`clear_caches` drops all of them at once. What belongs to one request is not
cached: the API client carries the caller's own access token, and sharing it would hand
one user's token to another user's turn.
"""

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool
from langchain_core.language_models import BaseChatModel

from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.service import AssistantService
from api.assistant.client import UserApiClient
from api.assistant.errors import AssistantRateLimitedError, AssistantUnavailableError
from api.assistant.rag.models import (
    LlamaServerReranker,
    make_answer_model,
    make_chat_model,
    make_embeddings,
)
from api.assistant.rag.retrieval import DocsRetriever, RetrievalConfig
from api.assistant.rag.store import make_engine, open_store
from api.assistant.rate_limit import AssistantThrottle, get_assistant_throttle
from api.assistant.upstream import UNAVAILABLE_ERRORS
from api.auth.dependencies import AccessToken, CurrentUser
from api.config import Settings, get_settings
from api.exceptions import ValidationError
from api.schemas.assistant import AssistantChatRequest
from api.utils.client_ip import get_client_ip

logger = logging.getLogger(__name__)


@contextmanager
def _outage_as_unavailable(settings: Settings) -> Iterator[None]:
    """Turn a backend that is down, while the vector store is opened, into a 503.

    The chat service does the same for what fails inside a turn, but the retriever is built
    by a dependency, before the service runs, and opening its store is the one place a
    dependency reaches a backend: the model clients are built without touching the network,
    and a model server that is down is met at generation time, inside the service. The
    record is the service's own: the event, the mode and the exception's class name, never
    its text. An error outside :data:`~api.assistant.upstream.UNAVAILABLE_ERRORS` is not
    touched. A failed build is not cached, so the next request tries again.

    :param settings: Application settings, for the mode written in the record.
    :raises AssistantUnavailableError: If a listed backend failure is raised inside.
    """
    try:
        yield
    except UNAVAILABLE_ERRORS as exc:
        logger.warning(
            "Assistant dependency unavailable",
            extra={
                "event": "assistant_dependency_unavailable",
                "mode": settings.assistant_mode,
                "reason": type(exc).__name__,
            },
        )
        raise AssistantUnavailableError("a server the assistant needs is unavailable") from None


@lru_cache
def get_answer_model() -> BaseChatModel:
    """Return the process-wide model that writes answers, built once from settings.

    :return: A chat model pointed at ``assistant_answer_llm_base_url``.
    """
    return make_answer_model(get_settings())


@lru_cache
def get_query_model() -> BaseChatModel:
    """Return the process-wide small model that translates search queries.

    It is not the answer model: it runs on its own server and never writes an answer.

    :return: A chat model pointed at ``assistant_llm_base_url``.
    """
    return make_chat_model(get_settings())


@lru_cache
def get_docs_retriever() -> DocsRetriever:
    """Return the process-wide documentation retriever, built once from settings.

    ``RetrievalConfig``'s own defaults are the search lab's measured winner; only the
    number of passages comes from ``assistant_retrieval_k``. The reranker and the query
    model are built only when the config asks for them.

    Opening the store reaches the vector database, so the first request of a process can
    meet a database that is down: that, and a missing ``ASSISTANT_VECTOR_DB_URL``, are
    ``AssistantUnavailableError``. A missing URL is logged by setting name only.

    :return: A retriever over the configured collection.
    :raises AssistantUnavailableError: If the vector database is down, or its URL is not set.
    """
    settings = get_settings()
    if not settings.assistant_vector_db_url:
        logger.warning(
            "Assistant vector database URL is not set",
            extra={"event": "assistant_setting_missing", "setting": "ASSISTANT_VECTOR_DB_URL"},
        )
        raise AssistantUnavailableError("the assistant's vector database is not configured")
    with _outage_as_unavailable(settings):
        config = RetrievalConfig(k=settings.assistant_retrieval_k)
        engine = make_engine(settings.assistant_vector_db_url)
        store = open_store(engine, settings.assistant_collection, make_embeddings(settings))
        reranker = (
            LlamaServerReranker(
                settings.assistant_rerank_base_url,
                settings.assistant_rerank_model,
                settings.assistant_llm_timeout_seconds,
            )
            if config.rerank
            else None
        )
        llm = get_query_model() if config.query_transform != "none" else None
        return DocsRetriever(store=store, config=config, reranker=reranker, llm=llm)


def clear_caches() -> None:
    """Drop every process-wide object this module keeps, so the next call builds anew.

    For tests and for a run that changes the settings; the models and the retriever
    read them once, when they are built.
    """
    get_answer_model.cache_clear()
    get_query_model.cache_clear()
    get_docs_retriever.cache_clear()


def get_assistant_service(
    settings: Annotated[Settings, Depends(get_settings)],
    answer_model: Annotated[BaseChatModel, Depends(get_answer_model)],
) -> AssistantService:
    """Build the per-request assistant service.

    :param settings: Application settings.
    :param answer_model: The process-wide model that writes answers.
    :return: A service ready to answer one turn.
    """
    return AssistantService(settings, answer_model)


AssistantServiceDep = Annotated[AssistantService, Depends(get_assistant_service)]
AssistantThrottleDep = Annotated[AssistantThrottle, Depends(get_assistant_throttle)]
DocsRetrieverDep = Annotated[DocsRetriever, Depends(get_docs_retriever)]


async def enforce_message_limit(current_user: CurrentUser, throttle: AssistantThrottleDep) -> None:
    """Spend one message of the caller's hourly budget, before anything else is built.

    Listed first among the route's dependencies, so a spent budget answers before the
    API client, the retriever's store or any model is touched. ``hit`` is synchronous
    and may talk to Redis, so it runs in a worker thread.

    :param current_user: The authenticated caller.
    :param throttle: The hourly message cap.
    :raises AssistantRateLimitedError: When this hour's budget is already spent.
    """
    if not await run_in_threadpool(throttle.hit, current_user.id):
        raise AssistantRateLimitedError("the hourly assistant message budget is spent")


@dataclass(frozen=True)
class PreparedTurn:
    """The parsed request and the context built for it.

    :ivar request: The validated chat request.
    :ivar context: The per-turn context, whose ``current_project_id`` and ``locale`` come
        from that same request.
    """

    request: AssistantChatRequest
    context: AssistantContext


def get_chat_request(
    data: AssistantChatRequest, settings: Annotated[Settings, Depends(get_settings)]
) -> AssistantChatRequest:
    """Validate the body and refuse a message longer than the configured length.

    A message longer than ``assistant_max_message_chars`` is an invalid request. The schema's
    own ceiling stays: the setting can only lower it. This is a dependency of its own, ahead
    of the retriever in :func:`open_chat_turn`, so a message over the configured length is
    refused before the retriever is built. A body the schema itself rejects is not: FastAPI
    keeps resolving the sibling dependencies after a body error, so the retriever may be
    built first, and on a cold start with the database down that request answers 503, not
    422.

    :param data: The validated chat request.
    :param settings: Application settings.
    :return: The same request.
    :raises ValidationError: If the message is longer than ``assistant_max_message_chars``.
    """
    if len(data.message) > settings.assistant_max_message_chars:
        raise ValidationError(
            f"message must not be longer than {settings.assistant_max_message_chars} characters"
        )
    return data


ChatRequestDep = Annotated[AssistantChatRequest, Depends(get_chat_request)]


async def open_chat_turn(
    request: Request,
    data: ChatRequestDep,
    access_token: AccessToken,
    retriever: DocsRetrieverDep,
) -> AsyncIterator[PreparedTurn]:
    """Build the API client and the context for one chat turn, and close the client after.

    The body is declared once, in :func:`get_chat_request`, which comes first among the
    parameters: the body is validated once, a message over the configured length is refused
    before the retriever is built (a body the schema rejects is not, see
    :func:`get_chat_request`), and the route and the context share the same request. The client
    is never cached: it carries this caller's own access token. It is closed when the
    response is done, whether the turn answered or failed. The retriever comes in through
    ``Depends``, so ``app.dependency_overrides`` can replace it.

    :param request: The incoming request, for its application and the caller's address.
    :param data: The checked chat request.
    :param access_token: The caller's own access token, the one the authentication
        dependency checked.
    :param retriever: The documentation retriever for this turn.
    :return: The request and its context.
    """
    client = UserApiClient(
        app=request.app, access_token=access_token, client_ip=get_client_ip(request)
    )
    context = AssistantContext(
        client=client,
        retriever=retriever,
        sources=SourceRegistry(),
        tool_outputs=[],
        current_project_id=None if data.project_id is None else str(data.project_id),
        locale=data.locale,
    )
    try:
        yield PreparedTurn(request=data, context=context)
    finally:
        await client.aclose()


PreparedTurnDep = Annotated[PreparedTurn, Depends(open_chat_turn)]
