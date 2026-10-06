"""Tests for the assistant chat request and response schemas."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.config import Settings
from api.schemas.assistant import (
    MAX_HISTORY_CONTENT_CHARS,
    MAX_HISTORY_ENTRIES,
    MAX_MESSAGE_CHARS,
    AnswerChecks,
    AssistantChatRequest,
    AssistantChatResponse,
    ChatTurn,
    SourceRef,
    TurnTiming,
    TurnUsage,
)


def _default(name: str) -> int:
    """Return a Settings field's declared default, ignoring any local .env."""
    return Settings.model_fields[name].default


class TestLimitsMatchSettings:
    """The schema bounds and the Settings defaults describe the same limits."""

    def test_history_bound_is_two_entries_per_configured_exchange(self):
        """
        GIVEN the default assistant_max_history_turns
        WHEN compared with the schema's history bound
        THEN the bound is twice that, one user and one assistant entry per exchange
        """
        assert 2 * _default("assistant_max_history_turns") == MAX_HISTORY_ENTRIES

    def test_message_bound_equals_the_configured_message_limit(self):
        """
        GIVEN the default assistant_max_message_chars
        WHEN compared with the schema's message bound
        THEN they are equal
        """
        assert _default("assistant_max_message_chars") == MAX_MESSAGE_CHARS


class TestChatTurn:
    """A history entry is a bounded user or assistant message."""

    @pytest.mark.parametrize("role", ["user", "assistant"])
    def test_accepts_the_two_chat_roles(self, role):
        """
        GIVEN a user or assistant role
        WHEN a ChatTurn is built
        THEN it is accepted
        """
        assert ChatTurn(role=role, content="hi").role == role

    @pytest.mark.parametrize("role", ["system", "tool", "developer", ""])
    def test_rejects_any_other_role(self, role):
        """
        GIVEN a role that could smuggle in instructions or tool output
        WHEN a ChatTurn is built
        THEN validation fails
        """
        with pytest.raises(ValidationError):
            ChatTurn(role=role, content="hi")

    def test_rejects_content_over_the_history_limit(self):
        """
        GIVEN a history entry one character over the history cap
        WHEN a ChatTurn is built
        THEN validation fails, and content at the cap, longer than a message, is accepted
        """
        assert ChatTurn(role="assistant", content="a" * MAX_HISTORY_CONTENT_CHARS)
        with pytest.raises(ValidationError):
            ChatTurn(role="assistant", content="a" * (MAX_HISTORY_CONTENT_CHARS + 1))

    def test_rejects_unknown_fields(self):
        """
        GIVEN a history entry with a field of its own
        WHEN a ChatTurn is built
        THEN an extra_forbidden error is raised
        """
        with pytest.raises(ValidationError) as exc_info:
            ChatTurn.model_validate({"role": "user", "content": "hi", "name": "x"})

        assert any(err["type"] == "extra_forbidden" for err in exc_info.value.errors())


class TestAssistantChatRequest:
    """The chat request bounds message size and history length."""

    def test_accepts_a_bare_message(self):
        """
        GIVEN only a message
        WHEN the request is built
        THEN history is empty, project_id is None and locale is English
        """
        request = AssistantChatRequest(message="What is Delta max?")

        assert request.history == []
        assert request.project_id is None
        assert request.locale == "en"

    def test_history_default_is_not_shared_between_requests(self):
        """
        GIVEN two requests built without history
        WHEN one history list is appended to
        THEN the other stays empty
        """
        first = AssistantChatRequest(message="a")
        second = AssistantChatRequest(message="b")

        first.history.append(ChatTurn(role="user", content="x"))

        assert second.history == []

    def test_rejects_an_empty_message(self):
        """
        GIVEN an empty message
        WHEN the request is built
        THEN validation fails
        """
        with pytest.raises(ValidationError):
            AssistantChatRequest(message="")

    @pytest.mark.parametrize("message", [" ", "   ", "\n\t", "\u00a0"])
    def test_rejects_a_whitespace_only_message(self, message):
        """
        GIVEN a message of only whitespace
        WHEN the request is built
        THEN validation fails
        """
        with pytest.raises(ValidationError):
            AssistantChatRequest(message=message)

    def test_a_valid_message_is_kept_exactly_as_sent(self):
        """
        GIVEN a message with leading and trailing whitespace around real text
        WHEN the request is built
        THEN the message is not stripped or otherwise altered
        """
        assert AssistantChatRequest(message="  hi\n").message == "  hi\n"

    def test_a_long_reply_replays_as_history_without_error(self):
        """
        GIVEN a history entry longer than a message may be
        WHEN the request is built
        THEN it is accepted
        """
        turn = ChatTurn(role="assistant", content="a" * (MAX_MESSAGE_CHARS + 1))

        assert AssistantChatRequest(message="and then?", history=[turn])

    def test_message_length_bound(self):
        """
        GIVEN messages at and one over the limit
        WHEN the request is built
        THEN the first is accepted and the second rejected
        """
        assert AssistantChatRequest(message="a" * MAX_MESSAGE_CHARS)
        with pytest.raises(ValidationError):
            AssistantChatRequest(message="a" * (MAX_MESSAGE_CHARS + 1))

    def test_history_length_bound(self):
        """
        GIVEN histories at and one over the limit
        WHEN the request is built
        THEN the first is accepted and the second rejected
        """
        turns = [ChatTurn(role="user", content="hi") for _ in range(MAX_HISTORY_ENTRIES + 1)]

        assert AssistantChatRequest(message="hi", history=turns[:MAX_HISTORY_ENTRIES])
        with pytest.raises(ValidationError):
            AssistantChatRequest(message="hi", history=turns)

    def test_project_id_parses_a_uuid(self):
        """
        GIVEN a UUID string as project_id
        WHEN the request is built
        THEN project_id is a UUID
        """
        project_id = uuid4()

        request = AssistantChatRequest.model_validate(
            {"message": "hi", "project_id": str(project_id)}
        )

        assert request.project_id == project_id

    def test_rejects_a_project_id_that_is_not_a_uuid(self):
        """
        GIVEN a project_id that is not a UUID
        WHEN the request is built
        THEN validation fails
        """
        with pytest.raises(ValidationError):
            AssistantChatRequest(message="hi", project_id="../etc/passwd")

    def test_rejects_an_unknown_locale(self):
        """
        GIVEN a locale the UI does not ship
        WHEN the request is built
        THEN validation fails
        """
        with pytest.raises(ValidationError):
            AssistantChatRequest(message="hi", locale="fr")


class TestSourceRef:
    """A source reference only accepts the two known corpus layers."""

    @pytest.mark.parametrize("layer", ["public", "local"])
    def test_accepts_public_and_local_layers(self, layer):
        """
        GIVEN each corpus layer
        WHEN a SourceRef is built
        THEN it is accepted
        """
        ref = SourceRef(n=1, title="Method", section="Intro", url=None, layer=layer)

        assert ref.layer == layer

    def test_rejects_an_unknown_layer(self):
        """
        GIVEN a layer the corpus does not define
        WHEN a SourceRef is built
        THEN validation fails
        """
        with pytest.raises(ValidationError):
            SourceRef(n=1, title="Method", section="Intro", url=None, layer="private")


class TestAssistantChatResponse:
    """The response bundles the answer with its sources, tools, and checks."""

    def test_round_trips_through_model_dump(self):
        """
        GIVEN a response with one source and passing checks
        WHEN it is dumped
        THEN the nested sources, checks and usage appear as plain data
        """
        response = AssistantChatResponse(
            answer="The compromise is 14.31 [1].",
            sources=[
                SourceRef(n=1, title="Worked example", section="Result", url=None, layer="public")
            ],
            tools_used=["search_docs"],
            checks=AnswerChecks(citations_valid=True, numbers_grounded=True, ungrounded_numbers=[]),
            usage=TurnUsage(
                input_tokens=120, output_tokens=30, total_tokens=150, llm_calls=2, complete=False
            ),
            timing=TurnTiming(ttft_ms=None, total_ms=1234),
        )

        dumped = response.model_dump()

        assert dumped["sources"][0]["n"] == 1
        assert dumped["checks"]["numbers_grounded"] is True
        assert dumped["tools_used"] == ["search_docs"]
        assert dumped["usage"] == {
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "llm_calls": 2,
            "complete": False,
        }
        assert dumped["timing"] == {"ttft_ms": None, "total_ms": 1234}

    def test_the_response_requires_timing(self):
        """
        GIVEN a response built without timing
        WHEN it is validated
        THEN it is refused
        """
        with pytest.raises(ValidationError):
            AssistantChatResponse(
                answer="x",
                sources=[],
                tools_used=[],
                checks=AnswerChecks(
                    citations_valid=True, numbers_grounded=True, ungrounded_numbers=[]
                ),
                usage=TurnUsage(
                    input_tokens=1, output_tokens=1, total_tokens=2, llm_calls=1, complete=True
                ),
            )


class TestTurnTiming:
    """A turn's timing says how long it took, and when the first token came."""

    def test_the_non_streamed_turn_has_no_first_token_time(self):
        """
        GIVEN a timing with no first-token time
        WHEN it is built
        THEN ttft_ms is None and total_ms is kept
        """
        timing = TurnTiming(ttft_ms=None, total_ms=1234)

        assert timing.ttft_ms is None
        assert timing.total_ms == 1234
