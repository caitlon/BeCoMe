"""Factories for the assistant's model clients: chat and embeddings.

Both point at a locally running llama-server (one process per role, BCM-121's spike),
reached through the OpenAI-compatible API langchain_openai speaks. The rerank role
(LlamaServerReranker) is not an OpenAI-shaped client - llama-server's /v1/rerank has no
langchain_openai counterpart - and is added in Task 124.11.
"""

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


def make_embeddings(settings: Settings) -> OpenAIEmbeddings:
    """Build the embeddings client, pointed at the local embedding llama-server.

    check_embedding_ctx_length=False is required: without it OpenAIEmbeddings sends
    tiktoken-encoded integer tokens instead of raw text, which llama-server's
    embedding endpoint does not accept.

    :param settings: Application settings.
    :return: An OpenAIEmbeddings client for settings.assistant_embedding_base_url.
    """
    return OpenAIEmbeddings(
        base_url=settings.assistant_embedding_base_url,
        api_key=SecretStr("not-needed"),
        model=settings.assistant_embedding_model,
        check_embedding_ctx_length=False,
    )
