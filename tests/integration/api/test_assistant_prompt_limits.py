"""Integration tests that pin what the assistant sends the answer model at the input limits.

The model server runs with a 16384-token window (``-c 16384`` in
``scripts/assistant/run-llama-servers.sh``). These tests hold two things: in workflow mode a
request with every input at its schema limit still fits that window, and in every mode a
model server that rejects a prompt as too long is a clean 503 with the fixed body, on both
routes, never a 500 and never the provider's own text. Models are stubs, the API the assistant
reads from is replaced by a client that answers with worst-case data, and no request leaves
the process.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from api.assistant import deps
from api.assistant.agent.service import _HISTORY_CHAR_BUDGET
from api.assistant.rag.models import make_answer_model
from api.assistant.rag.retrieval import RetrievedChunk
from api.assistant.views import FuzzyView, OpinionView, ProjectView, ResultView
from api.config import Settings, get_settings
from api.schemas.assistant import (
    MAX_HISTORY_CONTENT_CHARS,
    MAX_HISTORY_ENTRIES,
    MAX_MESSAGE_CHARS,
)
from api.schemas.project import (
    PROJECT_DESCRIPTION_MAX,
    PROJECT_NAME_MAX,
    PROJECT_SCALE_UNIT_MAX,
)
from tests.integration.api import test_assistant_chat as chat_tests
from tests.integration.api.conftest import register_and_login
from tests.integration.api.test_assistant_chat import (
    _ALL_MODES,
    CHAT,
    STREAM,
    UNAVAILABLE_BODY,
    _events,
    _scripted,
    _use_model,
)
from tests.shared.assistant_fakes import StaticDocsRetriever
from tests.shared.helpers import auth_header

# The chat tests' fixtures, reused as they are (see test_assistant_tool_boundaries.py).
_chat_settings = chat_tests._chat_settings
configure = chat_tests.configure

# The window of the answer model's server, in tokens.
_WINDOW_TOKENS = 16384
# Characters per token assumed for everything but digits. English prose runs near four;
# symbols, code and Czech text run lower, and a prompt of project data is mostly the latter.
# 2.5 is below all of them on purpose, so the estimate of the tokens errs on the high side.
_CHARS_PER_TOKEN = 2.5
# Digit runs tokenize near one character per token on Qwen-style tokenizers, so the estimate
# counts every digit as a whole token and only the other characters at _CHARS_PER_TOKEN.
_TOKENS_PER_DIGIT = 1.0


def _estimated_tokens(text: str) -> float:
    """Estimate the tokens of a text: one per digit, the rest at ``_CHARS_PER_TOKEN``."""
    digits = sum(character.isdigit() for character in text)
    return digits * _TOKENS_PER_DIGIT + (len(text) - digits) / _CHARS_PER_TOKEN


_PROJECT_ID = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"
# The longest a number reads in a project block: 15 digits, two decimals and a sign.
_WIDEST_NUMBER = -999_999_999_999_999.99
# Six more opinions than a block shows (50), so the "more opinions" line is written too.
_OPINIONS = 56
# The longest first plus last name an account can have: 100 characters each and a space.
_LONGEST_PERSON_NAME = "N" * 100 + " " + "N" * 100
# What the shipped corpus's longest passages measure (500-character chunks, titles up to 27
# and heading paths up to 111 characters), as many as the default retrieval k.
_CHUNK_CHARS, _TITLE_CHARS, _SECTION_CHARS = 500, 27, 111
_ANSWER = "The answer."
# What llama.cpp's server answers when a prompt does not fit its window.
_CONTEXT_SIZE_REJECTION = {
    "error": {
        "code": 400,
        "message": "the request exceeds the available context size, try increasing it",
        "type": "exceed_context_size_error",
        "n_prompt_tokens": 20000,
        "n_ctx": _WINDOW_TOKENS,
    }
}


def _text(width: int, prefix: str = "") -> str:
    """Return ``prefix`` followed by ordinary words, cut to exactly ``width`` characters."""
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu " * 400
    return (prefix + words)[:width]


class _WorstCaseClient:
    """Stands in for the user's API client: every read answers with the biggest data allowed."""

    def __init__(self, **_: Any) -> None:
        """Take the app, token and address the route passes, and keep none of them."""

    async def get_project(self, project_id: str) -> ProjectView:
        """Return a project whose name, description and unit are at their schema limits."""
        return ProjectView(
            id=project_id,
            name=_text(PROJECT_NAME_MAX),
            description=_text(PROJECT_DESCRIPTION_MAX),
            scale_min=_WIDEST_NUMBER,
            scale_max=-_WIDEST_NUMBER,
            scale_unit=_text(PROJECT_SCALE_UNIT_MAX),
            role="x" * 60,
        )

    async def get_result(self, project_id: str) -> ResultView:
        """Return a result whose every number is the widest one."""
        number = FuzzyView(
            lower=_WIDEST_NUMBER, peak=_WIDEST_NUMBER, upper=_WIDEST_NUMBER, centroid=_WIDEST_NUMBER
        )
        return ResultView(
            best_compromise=number,
            arithmetic_mean=number,
            median=number,
            max_error=_WIDEST_NUMBER,
            num_experts=_OPINIONS,
            agreement_level="y" * 60,
            likert_value=5,
            likert_decision="z" * 60,
            calculated_at=datetime.now(UTC),
        )

    async def get_opinions(self, project_id: str, *, full: bool = False) -> list[OpinionView]:
        """Return more opinions than a block shows, each with the longest name and position."""
        return [
            OpinionView(
                expert_name=f"{index:02d}" + _LONGEST_PERSON_NAME[2:],
                position=_text(255),
                lower_bound=_WIDEST_NUMBER,
                peak=_WIDEST_NUMBER,
                upper_bound=_WIDEST_NUMBER,
                centroid=_WIDEST_NUMBER,
            )
            for index in range(_OPINIONS)
        ]

    async def aclose(self) -> None:
        """Close nothing: the client holds no connection."""


def _longest_chunks(count: int) -> list[RetrievedChunk]:
    """Build passages of the longest size the corpus's splitter makes."""
    return [
        RetrievedChunk(
            text="caption " + _text(_CHUNK_CHARS, f"{index} "),
            title="T" * _TITLE_CHARS,
            section="S" * _SECTION_CHARS,
            url=None,
            layer="public",
            score=0.9,
            chunk_text=_text(_CHUNK_CHARS, f"{index} "),
        )
        for index in range(count)
    ]


def _entries(count: int, user_chars: int, assistant_chars: int) -> list[dict[str, str]]:
    """Build a history of alternating user and assistant entries of the given lengths."""
    return [
        {"role": "user", "content": _text(user_chars)}
        if index % 2 == 0
        else {"role": "assistant", "content": _text(assistant_chars)}
        for index in range(count)
    ]


class TestPromptAtTheInputLimits:
    """Every input at its limit still gives the answer model a prompt that fits its window."""

    @pytest.mark.parametrize(
        ("history", "history_chars", "kept_entries"),
        [
            # 10 user entries of 300 characters and 10 assistant entries of 264 plus the
            # 35-character wrapper: 5990 characters sent, inside the budget with slack, so
            # every entry is kept. A sum within one entry (300) of the budget shows the
            # budget is the limit that was reached.
            pytest.param(
                _entries(MAX_HISTORY_ENTRIES, 300, 264),
                range(_HISTORY_CHAR_BUDGET - 299, _HISTORY_CHAR_BUDGET + 1),
                range(MAX_HISTORY_ENTRIES, MAX_HISTORY_ENTRIES + 1),
                id="budget",
            ),
            # About 10,000 characters in 20 entries: the oldest are dropped until the rest
            # fits the budget, and what is kept starts with a user entry.
            pytest.param(
                _entries(MAX_HISTORY_ENTRIES, 500, 500),
                range(1, _HISTORY_CHAR_BUDGET + 1),
                range(1, MAX_HISTORY_ENTRIES),
                id="over the budget",
            ),
            pytest.param(
                _entries(MAX_HISTORY_ENTRIES, MAX_HISTORY_CONTENT_CHARS, MAX_HISTORY_CONTENT_CHARS),
                range(0, 1),
                range(0, 1),
                id="entries at the schema limit",
            ),
        ],
    )
    def test_the_workflow_prompt_fits_the_window_with_room_for_the_answer(
        self,
        assistant_settings,
        client,
        monkeypatch,
        history,
        history_chars,
        kept_entries,
    ):
        """
        GIVEN workflow mode with the default settings, a 4000-character message, 20 history
            entries, a project and a result at their limits, 56 opinions with the longest names
            and positions, and three of the longest passages from the retriever
        WHEN the question is posted
        THEN every limited part really reached the prompt at its limit (the history is as much
            as the budget keeps: all of it, the newest entries that fit starting with a user
            entry, or none when each entry alone is over it), and the prompt's estimated
            tokens plus the answer's allowance stay within the window
        """
        # GIVEN
        token = register_and_login(client, "prompt-limits@example.com")
        monkeypatch.setattr(deps, "UserApiClient", _WorstCaseClient)
        model = _scripted(_ANSWER)
        _use_model(client, model)
        chunks = _longest_chunks(get_settings().assistant_retrieval_k)
        client.app.dependency_overrides[deps.get_docs_retriever] = lambda: StaticDocsRetriever(
            chunks
        )
        message = _text(MAX_MESSAGE_CHARS, "What ")

        # WHEN
        response = client.post(
            CHAT,
            json={"message": message, "history": history, "project_id": _PROJECT_ID},
            headers=auth_header(token),
        )

        # THEN
        assert response.status_code == 200
        assert len(model.seen) == 1
        sent: list[BaseMessage] = model.seen[0]
        assert isinstance(sent[0], SystemMessage)
        assert isinstance(sent[-1], HumanMessage)
        last = sent[-1].text
        assert f"Question: {message}" in last
        assert sum(len(entry.text) for entry in sent[1:-1]) in history_chars
        assert len(sent[1:-1]) in kept_entries
        assert not sent[1:-1] or isinstance(sent[1], HumanMessage)
        assert "... and 6 more opinions" in last
        assert all(chunk.chunk_text in last for chunk in chunks)
        description = next(line for line in last.splitlines() if line.startswith("Description: "))
        assert len(description) > 1000
        prompt = "".join(entry.text for entry in sent)
        # Without its history the worst case measures 23,095 characters (about 29,000 with a
        # full history budget), so a shrunken prompt cannot pass.
        history_sent = sum(len(entry.text) for entry in sent[1:-1])
        assert len(prompt) - history_sent > 23_000
        answer_tokens = Settings.model_fields["assistant_answer_max_tokens"].default
        assert get_settings().assistant_answer_max_tokens == answer_tokens
        assert _estimated_tokens(prompt) + answer_tokens <= _WINDOW_TOKENS


def _use_rejecting_model(client: Any) -> list[httpx.Request]:
    """Make the app's answer model the real one, with a server that rejects every prompt.

    The server is a mock transport answering 400 in llama.cpp's shape, so the real client
    raises the real ``openai.BadRequestError`` with no connection made.

    :return: The requests that reached the mock server, so a test can show that the 503 came
        from this rejection and not from a failed connection.
    """
    requests: list[httpx.Request] = []

    def reject(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(400, json=_CONTEXT_SIZE_REJECTION)

    model = make_answer_model(get_settings())
    # Typed as Any: the openai package types its http client as httpx2's, the tests use httpx's.
    http_client: Any = httpx.AsyncClient(transport=httpx.MockTransport(reject))
    # The provider client's own class, built again around the mock transport.
    api_client = type(model.root_async_client)(
        api_key="unused",  # pragma: allowlist secret
        base_url="http://model.test/v1",
        http_client=http_client,
        max_retries=0,
    )
    model.root_async_client = api_client
    model.async_client = api_client.chat.completions
    _use_model(client, model)
    return requests


@pytest.mark.parametrize("mode", _ALL_MODES)
class TestPromptTooLongForTheModelServer:
    """A prompt the model server rejects as too long is a 503 with the fixed body."""

    def test_the_chat_route_answers_503_without_the_providers_text(
        self, assistant_settings, client, configure, mode
    ):
        """
        GIVEN a model server that rejects the prompt with its context-size error (HTTP 400)
        WHEN a question is posted to /chat in the mode
        THEN exactly one request reached the model server, and the answer is 503 with exactly
            the fixed body, carrying nothing the server said
        """
        # GIVEN
        configure(ASSISTANT_MODE=mode)
        token = register_and_login(client, f"too-long-{mode}@example.com")
        requests = _use_rejecting_model(client)

        # WHEN
        response = client.post(CHAT, json={"message": "hi"}, headers=auth_header(token))

        # THEN
        assert len(requests) == 1
        assert response.status_code == 503
        assert response.json() == UNAVAILABLE_BODY

    def test_the_stream_route_ends_in_a_503_error_event_without_the_providers_text(
        self, assistant_settings, client, configure, mode
    ):
        """
        GIVEN the same model server
        WHEN a question is posted to /chat/stream in the mode
        THEN exactly one request reached the model server, and the stream ends in one error
            event with exactly the fixed payload, with nothing the server said
        """
        # GIVEN
        configure(ASSISTANT_MODE=mode)
        token = register_and_login(client, f"too-long-stream-{mode}@example.com")
        requests = _use_rejecting_model(client)

        # WHEN
        response = client.post(STREAM, json={"message": "hi"}, headers=auth_header(token))

        # THEN
        assert len(requests) == 1
        events = _events(response.text)
        assert events == [("error", {"code": 503, "detail": UNAVAILABLE_BODY["detail"]})]
        assert "context" not in response.text
        assert "n_ctx" not in response.text
