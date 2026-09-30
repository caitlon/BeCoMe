"""Dependency factories for the assistant's chat route.

Kept out of ``api/dependencies.py`` on purpose: that module loads in every deployed
process, and nothing there may import langchain or openai. This one is imported only by
code that loads when ``settings.assistant_enabled`` is true.

What lives for the whole process is cached here: the two chat models and the
documentation retriever, which owns a BM25 index and the vector store's engine.
:func:`clear_caches` drops all of them at once.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from api.assistant.errors import AssistantUnavailableError
from api.assistant.rag.models import (
    LlamaServerReranker,
    make_answer_model,
    make_chat_model,
    make_embeddings,
)
from api.assistant.rag.retrieval import DocsRetriever, RetrievalConfig
from api.assistant.rag.store import make_engine, open_store
from api.assistant.upstream import UNAVAILABLE_ERRORS
from api.config import Settings, get_settings

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
