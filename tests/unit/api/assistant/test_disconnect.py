"""Unit tests for the helpers that stop a chat turn when its client goes away."""

import asyncio
import logging
from typing import Any

import pytest

from api.routes.assistant import _run_unless_disconnected, _wait_for_disconnect
from tests.shared.helpers import captured_log_records

ROUTE_LOGGER = "api.routes.assistant"


class _Request:
    """Stands in for a request: ``receive`` plays back the given messages, then waits.

    :ivar calls: How many times ``receive`` was awaited.
    """

    def __init__(self, *messages: dict[str, Any], then_wait: float | None = None) -> None:
        self._messages = list(messages)
        self._then_wait = then_wait
        self.calls = 0

    async def receive(self) -> dict[str, Any]:
        self.calls += 1
        if self._messages:
            return self._messages.pop(0)
        if self._then_wait is None:
            await asyncio.Event().wait()
        else:
            await asyncio.sleep(self._then_wait)
        return {"type": "http.disconnect"}


class _Failing:
    """Stands in for a request whose ``receive`` raises after a while."""

    def __init__(self, error: Exception, after: float) -> None:
        self._error = error
        self._after = after

    async def receive(self) -> dict[str, Any]:
        await asyncio.sleep(self._after)
        raise self._error


DISCONNECT = {"type": "http.disconnect"}
STRAY = {"type": "http.request", "body": b"", "more_body": False}


@pytest.mark.asyncio
class TestWaitForDisconnect:
    """The watcher returns on the disconnect and on nothing else."""

    async def test_it_returns_at_the_disconnect_message(self):
        """
        GIVEN a request whose first message is the disconnect
        WHEN the watcher runs
        THEN it returns after one message
        """
        request = _Request(DISCONNECT)

        await _wait_for_disconnect(request)  # type: ignore[arg-type]

        assert request.calls == 1

    async def test_it_skips_other_messages_until_the_disconnect(self):
        """
        GIVEN a request that sends two other messages before the disconnect
        WHEN the watcher runs
        THEN it returns only at the disconnect
        """
        request = _Request(STRAY, STRAY, DISCONNECT)

        await _wait_for_disconnect(request)  # type: ignore[arg-type]

        assert request.calls == 3


@pytest.mark.asyncio
class TestRunUnlessDisconnected:
    """The work runs to its end unless the client leaves first."""

    async def test_it_returns_what_the_work_returned(self):
        """
        GIVEN work that finishes at once and a client that stays
        WHEN it is run
        THEN its result is returned and no disconnect is logged
        """
        request = _Request()

        async def work() -> str:
            return "answer"

        with captured_log_records(ROUTE_LOGGER) as records:
            result = await _run_unless_disconnected(request, work(), "chat")  # type: ignore[arg-type]

        assert result == "answer"
        assert records == []

    async def test_it_raises_what_the_work_raised(self):
        """
        GIVEN work that fails and a client that stays
        WHEN it is run
        THEN the failure reaches the caller, so the handlers see it as before
        """
        request = _Request()

        async def work() -> str:
            raise ValueError("from the work")

        with pytest.raises(ValueError, match="from the work"):
            await _run_unless_disconnected(request, work(), "chat")  # type: ignore[arg-type]

    async def test_it_cancels_the_work_and_logs_when_the_client_leaves(self):
        """
        GIVEN work that never ends and a client that leaves after 50 ms
        WHEN it is run
        THEN None is returned, the work saw a cancellation, and one info record names the route
        """
        request = _Request(then_wait=0.05)
        cancelled = False

        async def work() -> str:
            nonlocal cancelled
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return "late"

        with captured_log_records(ROUTE_LOGGER) as records:
            result = await _run_unless_disconnected(request, work(), "chat_stream")  # type: ignore[arg-type]

        assert result is None
        assert cancelled
        (record,) = records
        assert record.levelno == logging.INFO
        assert (record.event, record.route) == ("assistant_client_disconnected", "chat_stream")
        assert 40 <= record.duration_ms < 2000

    async def test_a_watcher_that_fails_does_not_cancel_the_work(self):
        """
        GIVEN a request whose receive fails after 10 ms, as Starlette's middleware does on an
            unexpected message, and work that finishes after 100 ms
        WHEN it is run
        THEN the work is not cancelled and its result is returned, no disconnect is logged, and
            one warning names the route and the exception class but not its text
        """
        request = _Failing(RuntimeError("secret-detail"), after=0.01)
        cancelled = False

        async def work() -> str:
            nonlocal cancelled
            try:
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return "answer"

        with captured_log_records(ROUTE_LOGGER) as records:
            result = await _run_unless_disconnected(request, work(), "chat")  # type: ignore[arg-type]

        assert result == "answer"
        assert not cancelled
        assert [r for r in records if r.event == "assistant_client_disconnected"] == []
        (record,) = records
        assert record.levelno == logging.WARNING
        assert (record.event, record.route, record.reason) == (
            "assistant_disconnect_watch_failed",
            "chat",
            "RuntimeError",
        )
        assert "secret-detail" not in record.getMessage()

    async def test_the_work_still_fails_as_it_would_after_the_watcher_failed(self):
        """
        GIVEN a request whose receive fails after 10 ms and work that then raises
        WHEN it is run
        THEN the work's exception reaches the caller
        """
        request = _Failing(RuntimeError("watcher"), after=0.01)

        async def work() -> str:
            await asyncio.sleep(0.05)
            raise ValueError("from the work")

        with pytest.raises(ValueError, match="from the work"):
            await _run_unless_disconnected(request, work(), "chat")  # type: ignore[arg-type]

    async def test_the_work_wins_when_it_finishes_with_the_disconnect(self):
        """
        GIVEN work that finishes in the same moment the client leaves
        WHEN it is run
        THEN the finished result is returned, not None
        """
        request = _Request(DISCONNECT)

        async def work() -> str:
            return "answer"

        result = await _run_unless_disconnected(request, work(), "chat")  # type: ignore[arg-type]

        assert result == "answer"
