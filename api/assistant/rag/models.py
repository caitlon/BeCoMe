"""Factories for the assistant's model clients: chat, answer, embeddings, and rerank.

The chat, answer and embedding roles point at a locally running llama-server process each,
reached through the OpenAI-compatible API langchain_openai speaks, or, per role, at a hosted
OpenAI-compatible endpoint (settings ``assistant_*_provider`` set to "api"). The rerank role
(LlamaServerReranker) is not an OpenAI-shaped client - llama-server's /v1/rerank has no
langchain_openai counterpart - so it talks to the endpoint directly over HTTP instead.
"""

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from api.assistant.roles import UpstreamRole, tag_role
from api.config import Settings

# llama-server ignores the key, but the OpenAI client insists on one.
_LOCAL_API_KEY = SecretStr("not-needed")
# The answer model alone sets its retries: the hosted endpoint fails now and then for
# reasons a retry cures, a dead local server only gets slower with them.
_API_MAX_RETRIES = 2

# What a client of the OpenAI chat or embeddings API raises, in the places it reads a reply,
# when the 200 it got is not shaped like one: a ValueError for an HTML page or an error
# object, a TypeError for a null field, an AttributeError for a null message. A KeyError is not
# on the list: the library parses the reply into a model that always has the key, so no probe
# reached one.
_REPLY_SHAPE_ERRORS = (ValueError, TypeError, AttributeError)

# What decoding a reply that is not JSON raises, before the place above is reached: a
# JSONDecodeError for an empty, HTML or cut-off body or stream line, a UnicodeDecodeError for
# one cut in the middle of a multi-byte character.
_UNDECODABLE_REPLY = (json.JSONDecodeError, UnicodeDecodeError)

# What the library raises when it parses one chunk of a stream that is not a completion chunk,
# in ``_convert_chunk_to_generation_chunk``, which runs library code alone: the reply-shape
# errors above, and a KeyError for a chunk whose ``choices`` is an object.
_CHUNK_SHAPE_ERRORS = (*_REPLY_SHAPE_ERRORS, KeyError)


class MalformedModelResponseError(Exception):
    """Raised when a model, embedding or rerank server answers 200 with a body that is no reply.

    An HTML page from a proxy, an ``error`` object, a body without its ``choices`` or
    ``results``: the server failed to answer, as much as if it had refused the connection,
    so it is listed in :data:`~api.assistant.upstream.UNAVAILABLE_ERRORS`. It is not an
    ``AssistantError``, which the API's error handler would answer by itself. The message
    never holds any of the body.
    """


@contextmanager
def _upstream(role: UpstreamRole, malformed: tuple[type[Exception], ...]) -> Iterator[None]:
    """Write the role on whatever the server's client raises inside, and name a bad body.

    :param role: The role of the server the block talks to.
    :param malformed: The errors that, raised inside the block, mean the server's body was
        not a reply. They are raised again as :class:`MalformedModelResponseError`, and
        the original is not chained to it, so that nothing of the body reaches a log.
    :raises MalformedModelResponseError: For an error listed in ``malformed``.
    """
    try:
        yield
    except malformed:
        error = MalformedModelResponseError(f"the {role} server answered with a malformed body")
        tag_role(error, role)
        raise error from None
    except Exception as exc:
        tag_role(exc, role)
        raise


class _RoleTaggedChatOpenAI(ChatOpenAI):
    """A ChatOpenAI client whose failures say which role's server they came from.

    The client library turns a body that is no completion into a bare ``ValueError``,
    ``TypeError`` or ``AttributeError`` from the one method that reads the body, and a body
    that cannot be decoded into a ``json.JSONDecodeError`` or ``UnicodeDecodeError`` before
    that method runs. Those, and only those, are caught here, so a bug elsewhere in a call
    stays what it is. A stream is read chunk by chunk: a line that cannot be decoded is
    caught the same way, and a chunk of the wrong shape is caught where the library parses
    it (``_convert_chunk_to_generation_chunk``). The request is built and the callbacks run
    inside the same iteration, so nothing else is caught around it. A chunk that is JSON
    but not an object fails in the library's loop, before that method, and is not caught.
    Every call the assistant makes (``invoke``, ``ainvoke``, ``astream``, and
    a copy bound to tools or options, which shares this instance) ends in the three methods
    below; the synchronous ``_stream`` is not overridden, since nothing in ``api/`` streams
    synchronously. A stream has no body to read: an HTML page yields no chunk, and LangChain
    would then fail with a bare ``ValueError``, so a stream that ends without one is raised
    here as malformed.

    :ivar upstream_role: The role written on whatever a call raises.
    :ivar name: The name of the model's runs in a trace, kept as the library class's so that
        a subclass does not rename them.
    """

    upstream_role: UpstreamRole = "unknown"
    name: str | None = "ChatOpenAI"

    def _create_chat_result(
        self, response: Any, generation_info: dict[Any, Any] | None = None
    ) -> ChatResult:
        malformed = MalformedModelResponseError(
            f"the {self.upstream_role} server answered with a body that is not a completion"
        )
        try:
            result = super()._create_chat_result(response, generation_info)
        except _REPLY_SHAPE_ERRORS:
            raise malformed from None
        if not result.generations:
            # ``"choices": []`` parses, and the caller would then fail on an IndexError.
            raise malformed
        return result

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        with _upstream(self.upstream_role, _UNDECODABLE_REPLY):
            return super()._generate(*args, **kwargs)

    async def _agenerate(self, *args: Any, **kwargs: Any) -> ChatResult:
        with _upstream(self.upstream_role, _UNDECODABLE_REPLY):
            return await super()._agenerate(*args, **kwargs)

    def _convert_chunk_to_generation_chunk(
        self, chunk: dict[Any, Any], default_chunk_class: type, base_generation_info: Any
    ) -> ChatGenerationChunk | None:
        try:
            return super()._convert_chunk_to_generation_chunk(
                chunk, default_chunk_class, base_generation_info
            )
        except _CHUNK_SHAPE_ERRORS:
            raise MalformedModelResponseError(
                f"the {self.upstream_role} server streamed a chunk that is not a completion"
            ) from None

    async def _astream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        with _upstream(self.upstream_role, _UNDECODABLE_REPLY):
            yielded = False
            async for chunk in super()._astream(*args, **kwargs):
                yielded = True
                yield chunk
            if not yielded:
                raise MalformedModelResponseError(
                    f"the {self.upstream_role} server streamed no chunk at all"
                )


class _RoleTaggedEmbeddings(OpenAIEmbeddings):
    """An OpenAIEmbeddings client whose failures carry the role ``embedding``.

    The library does not check the body it gets: an HTML page raises an ``AttributeError``
    and a body without vectors a ``ValueError``, from inside the call, so those errors are
    caught around each of the four public methods and raised as
    :class:`MalformedModelResponseError`.
    """

    def embed_documents(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        with _upstream("embedding", _REPLY_SHAPE_ERRORS):
            return super().embed_documents(*args, **kwargs)

    def embed_query(self, *args: Any, **kwargs: Any) -> list[float]:
        with _upstream("embedding", _REPLY_SHAPE_ERRORS):
            return super().embed_query(*args, **kwargs)

    async def aembed_documents(self, *args: Any, **kwargs: Any) -> list[list[float]]:
        with _upstream("embedding", _REPLY_SHAPE_ERRORS):
            return await super().aembed_documents(*args, **kwargs)

    async def aembed_query(self, *args: Any, **kwargs: Any) -> list[float]:
        with _upstream("embedding", _REPLY_SHAPE_ERRORS):
            return await super().aembed_query(*args, **kwargs)


def _api_chat_extra_body(settings: Settings, hosted: bool) -> dict[str, str] | None:
    """Build the extra request body a hosted chat model sends.

    Hosted Qwen3.5 reasons by default and spends every token on it, returning no text; the
    reasoning_effort "none", measured on OVHcloud, turns the reasoning off. The
    enable_thinking forms are refused.

    :param settings: Application settings.
    :param hosted: Whether the role runs on the hosted API.
    :return: {"reasoning_effort": <setting>}, or None for a local role or an unset setting.
    """
    effort = settings.assistant_api_reasoning_effort
    if not hosted or effort is None:
        return None
    return {"reasoning_effort": effort}


def _api_key(settings: Settings, provider: str) -> SecretStr:
    """Pick the key a role sends: the hosted key in api mode, the placeholder otherwise.

    :param settings: Application settings.
    :param provider: The role's provider setting, "local" or "api".
    :return: assistant_api_key_ovh for an api role (Settings guarantees it is set), else
        the placeholder a local server ignores.
    """
    if provider == "api" and settings.assistant_api_key_ovh is not None:
        return settings.assistant_api_key_ovh
    return _LOCAL_API_KEY


def make_chat_model(settings: Settings) -> ChatOpenAI:
    """Build the chat model client, pointed at the chat llama-server or the hosted API.

    In api mode (settings.assistant_llm_provider) the client sends the hosted key and
    sends the configured ``reasoning_effort``; in local mode it is as it always was. The client
    keeps the SDK's own retries in both modes. A reply is capped at
    settings.assistant_query_max_tokens, which bounds a query transform and an index-time
    context sentence or summary alike.

    :param settings: Application settings.
    :return: A ChatOpenAI client for settings.assistant_llm_base_url, whose failures
        carry the role ``query``.
    """
    hosted = settings.assistant_llm_provider == "api"
    return _RoleTaggedChatOpenAI(
        upstream_role="query",
        base_url=settings.assistant_llm_base_url,
        api_key=_api_key(settings, settings.assistant_llm_provider),
        model=settings.assistant_llm_model,
        timeout=settings.assistant_llm_timeout_seconds,
        max_completion_tokens=settings.assistant_query_max_tokens,
        extra_body=_api_chat_extra_body(settings, hosted),
    )


def make_answer_model(settings: Settings) -> ChatOpenAI:
    """Build the client for the model that writes chat answers.

    Separate from make_chat_model, which serves the query transforms: the answer model
    is larger, runs on its own llama-server, and has its own token cap. Temperature 0
    keeps answers repeatable. A local server gets max_retries=0 because the OpenAI client
    otherwise retries twice, which triples the time a dead server takes to fail; the hosted
    API (settings.assistant_answer_provider = "api") gets two retries, its hosted key, and
    the reasoning switch of make_chat_model.

    :param settings: Application settings.
    :return: A ChatOpenAI client for settings.assistant_answer_llm_base_url, whose
        failures carry the role ``answer``.
    """
    hosted = settings.assistant_answer_provider == "api"
    return _RoleTaggedChatOpenAI(
        upstream_role="answer",
        base_url=settings.assistant_answer_llm_base_url,
        api_key=_api_key(settings, settings.assistant_answer_provider),
        model=settings.assistant_answer_llm_model,
        temperature=0,
        max_completion_tokens=settings.assistant_answer_max_tokens,
        max_retries=_API_MAX_RETRIES if hosted else 0,
        extra_body=_api_chat_extra_body(settings, hosted),
        # The last streamed chunk then carries the usage, which a streamed turn needs.
        stream_usage=True,
        timeout=settings.assistant_llm_timeout_seconds,
    )


THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


def strip_think_block(reply: str) -> str:
    """Remove the <think>...</think> block a reasoning-capable chat model may prepend.

    A locally swapped chat model can emit its internal reasoning inside a <think>
    block before the actual answer. Whatever the reply becomes, a context sentence
    stored with a chunk or a query to search with, that block would pollute it. Plain
    substring search, not a regular expression, keeps this linear in the reply's
    length.

    :param reply: The model's raw reply text.
    :return: reply without its first complete <think>...</think> block, stripped of
        leading and trailing whitespace. A reply with no complete block is only
        stripped.
    """
    start = reply.find(THINK_OPEN)
    end = reply.find(_THINK_CLOSE, start + len(THINK_OPEN)) if start != -1 else -1
    if end == -1:
        return reply.strip()
    return (reply[:start] + reply[end + len(_THINK_CLOSE) :]).strip()


def has_unclosed_think_block(reply: str) -> bool:
    """Say whether a reply ends inside a <think> block that never closes.

    Only the last opening tag counts: an earlier block is closed by the closing tag that
    follows it, and a closing tag written in the text with no opening tag before it is
    not a block at all. A reply cut off while the model was still reasoning is such a
    reply. It is not changed here, and :func:`strip_think_block` still keeps it as it is.

    :param reply: The model's raw reply text.
    :return: True when the last <think> has no </think> after it.
    """
    opened = reply.rfind(THINK_OPEN)
    return opened != -1 and _THINK_CLOSE not in reply[opened:]


# The embeddings client sends up to 1000 texts per request by default, and llama-server
# answers only once it has embedded all of them, so the request timeout must cover the
# whole batch. For llama-server, throughput does not depend on the batch size, so a small
# batch costs nothing.
# The hosted API (OVHcloud AI Endpoints) refuses more than 25 texts per request, so the batch
# stays below that.
_EMBEDDING_BATCH_SIZE = 16


def make_embeddings(settings: Settings) -> OpenAIEmbeddings:
    """Build the embeddings client, pointed at the embedding llama-server or the hosted API.

    check_embedding_ctx_length=False is required: without it OpenAIEmbeddings sends
    tiktoken-encoded integer tokens instead of raw text, which llama-server's
    embedding endpoint does not accept.

    There is no separate embedding timeout setting: settings.assistant_llm_timeout_seconds
    (the chat model's own timeout) bounds this client's requests too. Requests carry at
    most _EMBEDDING_BATCH_SIZE texts each, so that timeout bounds one small batch rather
    than the whole corpus.

    In api mode (settings.assistant_embedding_provider) the client sends the hosted key. The
    client keeps the SDK's own retries in both modes.

    :param settings: Application settings.
    :return: An OpenAIEmbeddings client for settings.assistant_embedding_base_url, whose
        failures carry the role ``embedding``.
    """
    return _RoleTaggedEmbeddings(
        base_url=settings.assistant_embedding_base_url,
        api_key=_api_key(settings, settings.assistant_embedding_provider),
        model=settings.assistant_embedding_model,
        check_embedding_ctx_length=False,
        timeout=settings.assistant_llm_timeout_seconds,
        chunk_size=_EMBEDDING_BATCH_SIZE,
    )


class LlamaServerReranker:
    """Async client for llama-server's /v1/rerank endpoint.

    Not an OpenAI-compatible client - langchain_openai has no rerank counterpart - so
    this talks to llama-server directly over HTTP, in the Jina/Cohere-shaped request
    and response llama.cpp documents for /v1/rerank.
    """

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        """
        :param base_url: The rerank-role llama-server's base URL, e.g.
            "http://127.0.0.1:8083/v1".
        :param model: Model alias the rerank llama-server was started with.
        :param timeout: HTTP request timeout, in seconds.
        """
        self._base_url = base_url
        self._model = model
        self._timeout = timeout

    async def rerank(self, query: str, texts: list[str]) -> list[float]:
        """Score each text's relevance to the query.

        A non-2xx response raises httpx.HTTPStatusError, and an unreachable server
        raises httpx.ConnectError, both as-is but tagged with the role ``rerank``. A 200
        whose body is not JSON, or holds no ``results`` list, raises
        MalformedModelResponseError. The chat endpoint's service layer is what turns any
        of them into AssistantUnavailableError.

        :param query: The search query.
        :param texts: Candidate passages, in the order to score.
        :return: One relevance score per text, in the SAME order as texts - not
            sorted by score. A caller that wants a ranking sorts the (text, score)
            pairs itself.
        :raises MalformedModelResponseError: if the response is not a JSON object with a
            ``results`` list.
        :raises ValueError: if a result's "index" falls outside range(len(texts)),
            if the response scores the same index more than once, or if it leaves
            any index in that range unscored.
        """
        with _upstream("rerank", (ValueError, KeyError, TypeError)):
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/rerank",
                    json={"model": self._model, "query": query, "documents": texts},
                )
            response.raise_for_status()
            results = response.json()["results"]
            if not isinstance(results, list):
                raise TypeError("results is not a list")
        scores = [0.0] * len(texts)
        seen_indices: set[int] = set()
        for result in results:
            index = result["index"]
            if not 0 <= index < len(texts):
                raise ValueError(
                    f"llama-server rerank result index {index} is out of range for "
                    f"{len(texts)} texts"
                )
            if index in seen_indices:
                raise ValueError(
                    f"llama-server rerank response scored index {index} more than once"
                )
            seen_indices.add(index)
            scores[index] = result["relevance_score"]
        missing_indices = sorted(set(range(len(texts))) - seen_indices)
        if missing_indices:
            raise ValueError(
                f"llama-server rerank response left indices {missing_indices} unscored"
            )
        return scores
