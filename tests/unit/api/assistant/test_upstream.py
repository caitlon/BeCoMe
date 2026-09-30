"""Tests for the list of failures that mean the assistant's backends are unavailable."""

import httpx
import openai
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from api.assistant.upstream import UNAVAILABLE_ERRORS

_REQUEST = httpx.Request("GET", "http://localhost/x")


class TestUnavailableErrors:
    """A connection, status or database failure is unavailability; a bug is not."""

    @pytest.mark.parametrize(
        "error",
        [
            openai.APIConnectionError(request=_REQUEST),
            openai.APITimeoutError(request=_REQUEST),
            openai.APIStatusError(
                "boom", response=httpx.Response(503, request=_REQUEST), body=None
            ),
            httpx.ConnectError("refused"),
            httpx.ReadTimeout("slow"),
            httpx.HTTPStatusError(
                "boom", request=_REQUEST, response=httpx.Response(502, request=_REQUEST)
            ),
            OperationalError("SELECT 1", {}, Exception("connection lost")),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_covers_a_failing_backend(self, error):
        """
        GIVEN an error a model server, an HTTP client or the database can raise
        WHEN it is checked against the list
        THEN it is on the list
        """
        assert isinstance(error, UNAVAILABLE_ERRORS)

    @pytest.mark.parametrize(
        "error",
        [
            RuntimeError("bug"),
            ValueError("bad input"),
            IntegrityError("INSERT", {}, Exception("duplicate")),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_leaves_a_bug_out(self, error):
        """
        GIVEN an ordinary programming or data error
        WHEN it is checked against the list
        THEN it is not on the list
        """
        assert not isinstance(error, UNAVAILABLE_ERRORS)
