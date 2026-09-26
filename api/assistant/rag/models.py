"""Factories for the assistant's model clients: chat, embeddings, and rerank.

The chat and embedding roles point at a locally running llama-server process each,
reached through the OpenAI-compatible API langchain_openai speaks. The rerank role
(LlamaServerReranker) is not an OpenAI-shaped client - llama-server's /v1/rerank has no
langchain_openai counterpart - so it talks to the endpoint directly over HTTP instead.
"""

import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from api.config import Settings


def make_chat_model(settings: Settings) -> ChatOpenAI:
    """Build the chat model client, pointed at the local chat llama-server.

    :param settings: Application settings.
    :return: A ChatOpenAI client for settings.assistant_llm_base_url.
    """
    return ChatOpenAI(
        base_url=settings.assistant_llm_base_url,
        api_key=SecretStr("not-needed"),
        model=settings.assistant_llm_model,
        timeout=settings.assistant_llm_timeout_seconds,
    )


_THINK_OPEN = "<think>"
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
    start = reply.find(_THINK_OPEN)
    end = reply.find(_THINK_CLOSE, start + len(_THINK_OPEN)) if start != -1 else -1
    if end == -1:
        return reply.strip()
    return (reply[:start] + reply[end + len(_THINK_CLOSE) :]).strip()


# The embeddings client sends up to 1000 texts per request by default, and llama-server
# answers only once it has embedded all of them, so the request timeout must cover the
# whole batch. Throughput does not depend on the batch size, so a small batch costs nothing.
_EMBEDDING_BATCH_SIZE = 64


def make_embeddings(settings: Settings) -> OpenAIEmbeddings:
    """Build the embeddings client, pointed at the local embedding llama-server.

    check_embedding_ctx_length=False is required: without it OpenAIEmbeddings sends
    tiktoken-encoded integer tokens instead of raw text, which llama-server's
    embedding endpoint does not accept.

    There is no separate embedding timeout setting: settings.assistant_llm_timeout_seconds
    (the chat model's own timeout) bounds this client's requests too. Requests carry at
    most 64 texts each, so that timeout bounds one small batch rather than the whole
    corpus.

    :param settings: Application settings.
    :return: An OpenAIEmbeddings client for settings.assistant_embedding_base_url.
    """
    return OpenAIEmbeddings(
        base_url=settings.assistant_embedding_base_url,
        api_key=SecretStr("not-needed"),
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

        Errors are not caught here: a non-2xx response raises httpx.HTTPStatusError,
        and an unreachable server raises httpx.ConnectError, both as-is. The chat
        endpoint's service layer is what turns either into AssistantUnavailableError.

        :param query: The search query.
        :param texts: Candidate passages, in the order to score.
        :return: One relevance score per text, in the SAME order as texts - not
            sorted by score. A caller that wants a ranking sorts the (text, score)
            pairs itself.
        :raises ValueError: if a result's "index" falls outside range(len(texts)),
            if the response scores the same index more than once, or if it leaves
            any index in that range unscored.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/rerank",
                json={"model": self._model, "query": query, "documents": texts},
            )
        response.raise_for_status()
        results = response.json()["results"]
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
