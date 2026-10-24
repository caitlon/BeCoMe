"""One look at each backend the assistant depends on, made when the process starts.

Without it the first user's question is the first request any of them gets, and a model
server with a wrong key, a missing collection or a dead embedding server is found by that
user. Each probe is a real request: only that checks the endpoint, the key and the model id
together. A failure is logged at ERROR with the role of the backend and the class of the
error, the same role names the 503 records carry (``api/assistant/roles.py``); the text of
an error is never logged, since it can name a host. Nothing here raises or stops the start.

This module is imported only when the assistant is enabled, by ``api/startup_checks.py``.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from langchain_core.language_models import BaseChatModel

from api.assistant.deps import get_answer_model, get_docs_retriever, get_query_model
from api.assistant.rag.models import LlamaServerReranker, make_embeddings
from api.assistant.rag.retrieval import RetrievalConfig
from api.assistant.roles import UpstreamRole
from api.assistant.upstream import role_of
from api.config import Settings

logger = logging.getLogger(__name__)

# The text every probe sends.
_PROBE_TEXT = "ping"

# The cap on a probe's completion, in tokens. A reply stopped by it is still a valid
# completion: LangChain raises only for a body with no choice at all, so an empty or cut-off
# text passes. Eight rather than one because a hosted endpoint may refuse the smallest caps.
_PROBE_MAX_TOKENS = 8


async def _probe_chat(model: BaseChatModel) -> None:
    """Ask a chat model for a few tokens.

    :param model: The answer or query model.
    """
    await model.bind(max_completion_tokens=_PROBE_MAX_TOKENS).ainvoke(_PROBE_TEXT)


async def _probe_embedding(settings: Settings) -> None:
    """Embed one short text with a client built from the settings, and close it.

    :param settings: Application settings.
    """
    embeddings = make_embeddings(settings)
    try:
        await embeddings.aembed_query(_PROBE_TEXT)
    finally:
        client = getattr(embeddings, "root_async_client", None)
        if client is not None:
            await client.close()


async def _probe_rerank(settings: Settings) -> None:
    """Rerank one short document.

    :param settings: Application settings.
    """
    reranker = LlamaServerReranker(
        settings.assistant_rerank_base_url,
        settings.assistant_rerank_model,
        settings.assistant_llm_timeout_seconds,
    )
    await reranker.rerank(_PROBE_TEXT, [_PROBE_TEXT])


def _probes(settings: Settings) -> dict[UpstreamRole, Callable[[], Awaitable[None]]]:
    """List the probes this deployment needs, by the role each one checks.

    The query model and the reranker are probed only when the retrieval config uses them,
    as :func:`api.assistant.deps.get_docs_retriever` builds them.

    :param settings: Application settings.
    :return: One probe per backend in use.
    """
    config = RetrievalConfig(k=settings.assistant_retrieval_k)

    async def vector_db() -> None:
        # Builds the retriever and keeps it, so the first question finds it ready.
        await asyncio.to_thread(get_docs_retriever)

    async def answer() -> None:
        await _probe_chat(get_answer_model())

    async def query() -> None:
        await _probe_chat(get_query_model())

    probes: dict[UpstreamRole, Callable[[], Awaitable[None]]] = {
        "vector_db": vector_db,
        "embedding": lambda: _probe_embedding(settings),
        "answer": answer,
    }
    if config.query_transform != "none":
        probes["query"] = query
    if config.rerank:
        probes["rerank"] = lambda: _probe_rerank(settings)
    return probes


async def _run_probe(
    role: UpstreamRole, probe: Callable[[], Awaitable[None]], timeout: float
) -> bool:
    """Run one probe under a time bound, logging an ERROR if it fails.

    A probe that runs in a worker thread (the document index) is abandoned at the bound, not
    stopped; the thread ends when its own timeouts do.

    :param role: The role of the backend the probe checks, used for a failure that carries
        no role of its own.
    :param probe: The probe.
    :param timeout: The most seconds to wait for the probe.
    :return: True if the probe passed.
    """
    try:
        await asyncio.wait_for(probe(), timeout)
    except Exception as exc:
        logger.error(
            "Assistant backend check failed at startup",
            extra={
                "event": "assistant_backend_check_failed",
                "role": role_of(exc, default=role),
                "reason": type(exc).__name__,
            },
        )
        return False
    return True


async def check_assistant_backends(settings: Settings) -> None:
    """Probe every backend of the assistant at once, and log what failed.

    One ERROR per failing backend, and, when all pass, one INFO record with the number of
    backends checked and the time it took. Each probe is bounded by
    ``assistant_llm_timeout_seconds``; one that runs out is a failure with reason
    ``TimeoutError``.

    :param settings: Application settings.
    """
    started = time.monotonic()
    probes = _probes(settings)
    timeout = settings.assistant_llm_timeout_seconds
    passed = await asyncio.gather(
        *(_run_probe(role, probe, timeout) for role, probe in probes.items())
    )
    if all(passed):
        logger.info(
            "Assistant backends checked at startup",
            extra={
                "event": "assistant_backends_checked",
                "checked": len(probes),
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
