"""Keeps the text of a pipeline command out of the Redis errors the application logs.

redis-py rewrites the message of an error a pipeline raises: it puts ``Command # <n>``, the
text of the failed command, key included, and ``of pipeline caused error:`` in front of the
server's reason. A store that logs such an error with its traceback, or copies its message,
would write that command text into a log record and, since every ERROR record becomes an
event, into the error tracker. :func:`drop_pipeline_command` cuts the message back to the
server's reason. A connection or timeout error is not rewritten, and the host and port of the
application's own store stay in it.
"""

import re

import redis

# redis-py's wording (``Pipeline.annotate_exception``): the command text sits between the
# brackets. The match is greedy so that a command which holds the closing wording itself is
# dropped whole, up to the last occurrence.
_PIPELINE_PREFIX = re.compile(r"Command # \d+ \(.*\) of pipeline caused error: ", re.DOTALL)


def drop_pipeline_command(exc: BaseException) -> None:
    """Cut the command text out of a pipeline error's message, in place.

    The same object is the cause of the error a store raises and the one a log record and an
    error event render, so a single reduction covers all of them. An error redis-py did not
    rewrite is left as it is.

    :param exc: The error a Redis call raised.
    """
    if not isinstance(exc, redis.ResponseError) or not exc.args:
        return
    message = exc.args[0]
    if not isinstance(message, str):
        return
    prefix = _PIPELINE_PREFIX.match(message)
    if prefix is not None:
        exc.args = (message[prefix.end() :], *exc.args[1:])
