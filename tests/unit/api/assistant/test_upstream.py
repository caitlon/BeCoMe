"""Tests for the list of failures that mean the assistant's backends are unavailable."""

import httpx
import openai
import pytest
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from api.assistant.errors import AssistantUpstreamError
from api.assistant.rag.models import MalformedModelResponseError
from api.assistant.rag.store import CollectionUnavailableError
from api.assistant.roles import tag_role
from api.assistant.upstream import UNAVAILABLE_ERRORS, role_of

_REQUEST = httpx.Request("GET", "http://localhost/x")


class TestUnavailableErrors:
    """A connection, status or database failure is unavailability; a bug is not."""

    @pytest.mark.parametrize(
        "error",
        [
            openai.APIConnectionError(request=_REQUEST),
            openai.APITimeoutError(request=_REQUEST),
            openai.APIError("boom", request=_REQUEST, body=None),
            openai.APIStatusError(
                "boom", response=httpx.Response(503, request=_REQUEST), body=None
            ),
            httpx.ConnectError("refused"),
            httpx.ReadTimeout("slow"),
            httpx.HTTPStatusError(
                "boom", request=_REQUEST, response=httpx.Response(502, request=_REQUEST)
            ),
            OperationalError("SELECT 1", {}, Exception("connection lost")),
            InterfaceError("SELECT 1", {}, Exception("connection closed")),
            PoolTimeoutError("QueuePool limit of size 5 overflow 10 reached"),
            ConnectionRefusedError("refused"),
            ConnectionResetError("reset"),
            CollectionUnavailableError("collection 'docs' cannot be opened"),
            MalformedModelResponseError("the answer server answered with a malformed body"),
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


class TestRoleOf:
    """The role of a failure is what its source wrote on it, else what its class says."""

    def test_a_tag_written_at_the_source_wins(self):
        """
        GIVEN a database error that the application client tagged app_api
        WHEN its role is read
        THEN it is app_api, not the vector_db its class alone would say
        """
        error = OperationalError("SELECT 1", {}, Exception("the application's database"))
        tag_role(error, "app_api")

        assert role_of(error) == "app_api"

    @pytest.mark.parametrize(
        "error",
        [
            OperationalError("SELECT 1", {}, Exception("lost")),
            InterfaceError("SELECT 1", {}, Exception("closed")),
            PoolTimeoutError("QueuePool limit reached"),
            CollectionUnavailableError("collection 'docs' cannot be opened"),
        ],
        ids=lambda e: type(e).__name__,
    )
    def test_an_untagged_database_error_is_the_vector_db(self, error):
        """
        GIVEN a database or collection failure nothing tagged
        WHEN its role is read
        THEN it is vector_db
        """
        assert role_of(error) == "vector_db"

    def test_an_upstream_error_of_the_api_client_is_app_api(self):
        """
        GIVEN the error the application client raises for an answer it cannot use
        WHEN its role is read
        THEN it is app_api
        """
        assert role_of(AssistantUpstreamError("/x returned 500")) == "app_api"

    def test_an_ambiguous_failure_is_unknown_or_the_callers_default(self):
        """
        GIVEN a bare httpx error that nothing tagged
        WHEN its role is read
        THEN it is unknown, or the default the caller knows from where it was caught
        """
        error = httpx.ConnectError("refused")

        assert role_of(error) == "unknown"
        assert role_of(error, default="vector_db") == "vector_db"
