"""Integration tests that pin the limits on one chat request, on both chat routes.

A request over a limit of the schema, or over the configured message length, is refused with
422 before anything is spent: no message of the hourly budgets, no turn slot, no model call.
The same request one step inside the limit is answered, so each refusal is about the limit
and about nothing else. The model is a scripted one that records what it is shown.
"""

import pytest

from api.assistant import deps
from tests.integration.api import test_assistant_chat as chat_tests
from tests.integration.api.conftest import register_and_login
from tests.integration.api.test_assistant_chat import (
    CHAT,
    STREAM,
    _events,
    _scripted,
    _use_model,
    _watched_budgets,
)
from tests.shared.helpers import auth_header

# The chat tests' fixtures, reused as they are (see test_assistant_tool_boundaries.py).
_chat_settings = chat_tests._chat_settings
configure = chat_tests.configure


def _history(entries: int, chars: int = 2) -> list[dict[str, str]]:
    """Build a history of alternating user and assistant entries of ``chars`` characters."""
    return [
        {"role": "user" if index % 2 == 0 else "assistant", "content": "h" * chars}
        for index in range(entries)
    ]


# The numbers are the limits written out, so that raising one fails here instead of moving the
# test along with it. The history rows pin the schema's ceilings. The 4001-character row is
# refused by the schema, but it pins the effective ceiling only: with the schema bound raised
# alone, the configured length (4000 here, capped by its own ``le=``) would still refuse it. The
# two bounds on their own are pinned in tests/unit/api/schemas/test_assistant.py and
# tests/unit/api/test_config.py.
# Each case is the configuration it needs, a request over a limit, and the same request
# exactly at that limit.
_CASES = {
    "the configured message length": (
        {"ASSISTANT_MAX_MESSAGE_CHARS": "50"},
        {"message": "m" * 51},
        {"message": "m" * 50},
    ),
    "the schema's message length": (
        {},
        {"message": "m" * 4001},
        {"message": "m" * 4000},
    ),
    "the number of history entries": (
        {},
        {"message": "hi", "history": _history(21)},
        {"message": "hi", "history": _history(20)},
    ),
    "the length of a history entry": (
        {},
        {"message": "hi", "history": _history(1, 8001)},
        {"message": "hi", "history": _history(1, 8000)},
    ),
}


class TestRequestOverALimit:
    """A request over a limit is a 422 that spends nothing and reaches no model."""

    @pytest.mark.parametrize("endpoint", [CHAT, STREAM])
    @pytest.mark.parametrize(("env", "over", "at_limit"), _CASES.values(), ids=_CASES.keys())
    def test_the_refusal_spends_nothing_and_a_request_at_the_limit_is_answered(
        self,
        assistant_settings,
        client,
        configure,
        endpoint,
        env,
        over,
        at_limit,
    ):
        """
        GIVEN a request one step over a limit, and the same request exactly at it
        WHEN the first is posted, and then the second
        THEN the first is 422 with no message spent from either budget, no turn slot held and
            the model never shown anything, and the second is answered, with the model shown
            the turn and each budget charged once
        """
        # GIVEN
        configure(**env)
        token = register_and_login(client, "input-limits@example.com")
        model = _scripted("Fine.")
        _use_model(client, model)

        with _watched_budgets() as (user_spy, global_spy):
            # WHEN
            refused = client.post(endpoint, json=over, headers=auth_header(token))

            # THEN
            assert refused.status_code == 422
            assert (user_spy.call_count, global_spy.call_count) == (0, 0)
            assert deps.get_turn_slots().holders == {}
            assert model.seen == []
            answered = client.post(endpoint, json=at_limit, headers=auth_header(token))
            assert answered.status_code == 200
            if endpoint == STREAM:
                names = [name for name, _ in _events(answered.text)]
                assert "error" not in names
                assert names[-1] == "done"
            assert len(model.seen) == 1
            assert (user_spy.call_count, global_spy.call_count) == (1, 1)
            assert deps.get_turn_slots().holders == {}
