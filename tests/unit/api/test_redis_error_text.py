"""Tests for the reduction of a Redis pipeline error to the server's reason."""

import pytest
import redis

from api.redis_error_text import drop_pipeline_command

_REASON = "You can't write against a read only replica."
_KEY = "session:current:sentinel-session"


def _annotated(number: int, command: str, reason: str = _REASON) -> redis.ReadOnlyError:
    """Build an error worded the way redis-py words a failed command of a pipeline."""
    return redis.ReadOnlyError(f"Command # {number} ({command}) of pipeline caused error: {reason}")


class TestDropPipelineCommand:
    """The command redis-py writes into a pipeline error is dropped; nothing else changes."""

    def test_an_annotated_message_is_reduced_to_the_servers_reason(self):
        """
        GIVEN a ReadOnlyError worded as redis-py words a failed pipeline command
        WHEN the command text is dropped
        THEN the message is the server's reason alone and the class is unchanged
        """
        # GIVEN
        exc = _annotated(1, f"SET {_KEY} 1 EX 60")

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert str(exc) == _REASON
        assert isinstance(exc, redis.ReadOnlyError)

    def test_a_command_with_brackets_and_the_wording_in_it_is_dropped_whole(self):
        """
        GIVEN an annotated message whose command text holds a closing bracket and the
            annotation's own wording
        WHEN the command text is dropped
        THEN nothing of the command is left, because the cut is at the last annotation
        """
        # GIVEN
        command = f"SET {_KEY}) of pipeline caused error: (x) 1"
        exc = _annotated(12, command)

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert str(exc) == _REASON

    def test_a_truncated_command_is_dropped(self):
        """
        GIVEN an annotated message whose command text redis-py cut short with an ellipsis
        WHEN the command text is dropped
        THEN the message is the server's reason alone
        """
        # GIVEN
        exc = _annotated(2, f"SET {_KEY} " + "x" * 90 + "...")

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert str(exc) == _REASON

    def test_a_command_with_a_newline_is_dropped_whole(self):
        """
        GIVEN an annotated message whose command text holds a line break
        WHEN the command text is dropped
        THEN the message is the server's reason alone
        """
        # GIVEN
        exc = _annotated(3, f"SET {_KEY}\nsecond line 1")

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert str(exc) == _REASON

    def test_the_other_arguments_of_the_error_are_kept(self):
        """
        GIVEN an annotated error that carries a second argument
        WHEN the command text is dropped
        THEN only the first argument changes
        """
        # GIVEN
        exc = redis.ResponseError(
            f"Command # 1 (DEL {_KEY}) of pipeline caused error: {_REASON}", "detail"
        )

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert exc.args == (_REASON, "detail")

    def test_dropping_twice_changes_nothing_more(self):
        """
        GIVEN an error whose command text was dropped
        WHEN it is dropped again
        THEN the message is the same
        """
        # GIVEN
        exc = _annotated(1, f"SET {_KEY} 1")
        drop_pipeline_command(exc)

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert str(exc) == _REASON

    @pytest.mark.parametrize(
        "exc",
        [
            redis.ReadOnlyError(_REASON),
            redis.ResponseError("ERR Command # 1 (GET k) of pipeline caused error: x"),
            redis.ConnectionError("Error 61 connecting to 127.0.0.1:6379. Connection refused."),
            redis.TimeoutError("Timeout reading from 127.0.0.1:6379"),
            redis.ResponseError(),
            redis.ResponseError(b"Command # 1 (GET k) of pipeline caused error: x"),
            redis.ResponseError(7),
            ValueError("Command # 1 (GET k) of pipeline caused error: x"),
        ],
        ids=[
            "single-command error",
            "text that does not start the way redis-py's annotation does",
            "connection error naming host and port",
            "timeout naming host and port",
            "error without arguments",
            "bytes argument",
            "non-text argument",
            "not a Redis error",
        ],
    )
    def test_anything_else_is_left_as_it_was(self, exc):
        """
        GIVEN an error that is not an annotated pipeline error
        WHEN the command text is dropped
        THEN its arguments are unchanged
        """
        # GIVEN
        before = exc.args

        # WHEN
        drop_pipeline_command(exc)

        # THEN
        assert exc.args == before
