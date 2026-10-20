"""Dependency factories for the assistant's chat route.

Kept out of ``api/dependencies.py`` on purpose: that module loads in every deployed
process, and nothing there may import langchain or openai. This one is imported only by
code that loads when ``settings.assistant_enabled`` is true.

What lives for the whole process is cached here: the two chat models, the
documentation retriever, which owns a BM25 index and the vector store's engine, and the
table of turn slots. :func:`clear_caches` drops all of them at once. What belongs to one
request is not cached: the API client carries the caller's own access token, and sharing it
would hand one user's token to another user's turn.
"""

import asyncio
import contextlib
import logging
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Request
from fastapi.concurrency import run_in_threadpool
from langchain_core.language_models import BaseChatModel

from api.assistant.agent.context import AssistantContext, SourceRegistry
from api.assistant.agent.service import AssistantService
from api.assistant.client import UserApiClient
from api.assistant.errors import (
    AssistantBusyError,
    AssistantRateLimitedError,
    AssistantUnavailableError,
)
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

# The cap on one statement of the retriever's searches, in milliseconds (see make_engine).
_STATEMENT_TIMEOUT_MS = 30000

# The most turns one user may have running at once, so one account cannot hold every slot.
MAX_TURNS_PER_USER = 2

# What a turn refused for want of a free slot is told to wait, in seconds.
TURN_SLOT_RETRY_SECONDS = 5


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
    meet a database that is down, or a collection that is missing: that, and a missing
    ``ASSISTANT_VECTOR_DB_URL``, are ``AssistantUnavailableError``. A missing URL is logged
    by setting name only. A build that fails closes its engine first.

    :return: A retriever over the configured collection.
    :raises AssistantUnavailableError: If the vector database is down, the collection cannot be
        opened, or the URL is not set.
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
        engine = make_engine(
            settings.assistant_vector_db_url, statement_timeout_ms=_STATEMENT_TIMEOUT_MS
        )
        try:
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
        except Exception:
            # A failed build is not cached, so every request would build another pool:
            # release this one before the error goes on, and let a failing close not
            # replace that error.
            with contextlib.suppress(Exception):
                asyncio.run(engine.close())
            raise


class TurnSlots:
    """Count the turns a process is answering, in all and per user, without ever waiting.

    The routes call it from the event loop, so the lock is not needed there; it is kept as
    cheap safety in case a worker thread ever calls it.

    :param max_total: The most turns the process answers at once.
    :param max_per_user: The most turns one user has running at once.
    :ivar max_total: The most turns the process answers at once.
    :ivar max_per_user: The most turns one user has running at once.
    :ivar holders: Turns running now, by user id; a user with none has no entry.
    """

    def __init__(self, max_total: int, max_per_user: int) -> None:
        self.max_total = max_total
        self.max_per_user = max_per_user
        self.holders: dict[UUID, int] = {}
        self._total = 0
        self._lock = threading.Lock()

    def acquire(self, user_id: UUID) -> Literal["process", "user"] | None:
        """Take a slot for this user if both limits leave room.

        :param user_id: The user whose turn asks.
        :return: ``None`` when the slot was taken, else the limit that refused it: the
            process-wide one is named first when both are reached.
        """
        with self._lock:
            if self._total >= self.max_total:
                return "process"
            if self.holders.get(user_id, 0) >= self.max_per_user:
                return "user"
            self._total += 1
            self.holders[user_id] = self.holders.get(user_id, 0) + 1
            return None

    def release(self, user_id: UUID) -> None:
        """Give back a slot this user took with :meth:`acquire`.

        A user who holds no slot changes nothing: the count is left as it was.

        :param user_id: The user whose turn is done.
        """
        with self._lock:
            held = self.holders.get(user_id)
            if held is None:
                return
            self._total -= 1
            if held == 1:
                del self.holders[user_id]
            else:
                self.holders[user_id] = held - 1


@lru_cache
def get_turn_slots() -> TurnSlots:
    """Return the process-wide table of turn slots, sized from settings when first built.

    :return: A table allowing ``assistant_max_concurrent_turns`` turns at once, and
        :data:`MAX_TURNS_PER_USER` for one user.
    """
    return TurnSlots(get_settings().assistant_max_concurrent_turns, MAX_TURNS_PER_USER)


def clear_caches() -> None:
    """Drop every process-wide object this module keeps, so the next call builds anew.

    For tests and for a run that changes the settings; the models, the retriever and the
    turn slots read them once, when they are built.
    """
    get_answer_model.cache_clear()
    get_query_model.cache_clear()
    get_docs_retriever.cache_clear()
    get_turn_slots.cache_clear()


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
TurnSlotsDep = Annotated[TurnSlots, Depends(get_turn_slots)]
DocsRetrieverDep = Annotated[DocsRetriever, Depends(get_docs_retriever)]


async def enforce_message_limit(current_user: CurrentUser, throttle: AssistantThrottleDep) -> None:
    """Spend one message of the caller's hourly budget, before anything else is built.

    Listed right after :func:`hold_turn_slot` among the route's dependencies, so a process
    that is full refuses first and spends no message, and a spent budget answers before the
    API client, the retriever's store or any model is touched. ``hit`` is synchronous
    and may talk to Redis, so it runs in a worker thread, as does ``retry_after``, which is
    asked only after a refusal.

    :param current_user: The authenticated caller.
    :param throttle: The hourly message cap.
    :raises AssistantRateLimitedError: When this hour's budget is already spent; it carries
        the seconds until the window closes.
    """
    if not await run_in_threadpool(throttle.hit, current_user.id):
        retry_after = await run_in_threadpool(throttle.retry_after, current_user.id)
        raise AssistantRateLimitedError(
            "the hourly assistant message budget is spent", retry_after=retry_after
        )


async def hold_turn_slot(current_user: CurrentUser, slots: TurnSlotsDep) -> AsyncIterator[None]:
    """Hold one of the process's turn slots until the response is done, or refuse at once.

    Listed first on both chat routes, ahead of :func:`enforce_message_limit`: a turn refused
    for want of a slot spends no message of the hourly budget, and a turn the budget refuses
    gives its slot back when the dependency exits. A slot is taken without waiting, since a
    queue of requests behind a slow model server would only hold workers: a turn is refused
    when the process is answering its limit of turns, or when this user already has
    :data:`MAX_TURNS_PER_USER` running. The code after ``yield`` runs once the response has
    been sent, so a streamed answer holds its slot for the whole stream. The slot is given
    back whether the turn answered or failed, and only when this call took it. It
    writes no record: the handler of :class:`AssistantBusyError` writes the one.

    :param current_user: The authenticated caller.
    :param slots: The process-wide table from :func:`get_turn_slots`.
    :raises AssistantBusyError: If no slot is free for this turn; it carries
        :data:`TURN_SLOT_RETRY_SECONDS` and the limit that refused.
    """
    refused_by = slots.acquire(current_user.id)
    if refused_by is not None:
        raise AssistantBusyError(
            "no assistant turn slot is free",
            retry_after=TURN_SLOT_RETRY_SECONDS,
            reason=refused_by,
        )
    try:
        yield
    finally:
        slots.release(current_user.id)


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
