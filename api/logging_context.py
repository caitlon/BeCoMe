"""Request-scoped logging context propagated via context variables.

The request-logging middleware and the auth dependency bind the active
``request_id`` and ``user_id`` here, and :class:`ContextFilter` copies them onto
every ``api.*`` log record. This makes the correlation ID and the acting user
queryable on service- and security-layer logs, not just on the request line,
without threading them through every function signature.
"""

import logging
from contextvars import ContextVar, Token

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind the correlation ID for the current context.

    :param request_id: Correlation ID for the active request.
    :return: Reset token to restore the previous value.
    """
    return _request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the correlation ID to its previous value.

    :param token: Token returned by :func:`set_request_id`.
    """
    _request_id_var.reset(token)


def get_request_id() -> str | None:
    """Return the correlation ID bound to the current context.

    :return: Active correlation ID, or ``None`` when unset.
    """
    return _request_id_var.get()


def set_user_id(user_id: str) -> Token[str | None]:
    """Bind the acting user ID for the current context.

    :param user_id: ID of the authenticated user driving the request.
    :return: Reset token to restore the previous value.
    """
    return _user_id_var.set(user_id)


def reset_user_id(token: Token[str | None]) -> None:
    """Restore the acting user ID to its previous value.

    :param token: Token returned by :func:`set_user_id`.
    """
    _user_id_var.reset(token)


def get_user_id() -> str | None:
    """Return the acting user ID bound to the current context.

    :return: Active user ID, or ``None`` when unset.
    """
    return _user_id_var.get()


class ContextFilter(logging.Filter):
    """Copy the request-scoped context onto each log record.

    Attached to the ``api`` logger's handlers, so records from every child logger
    (``api.service.*``, ``api.security``, ...) gain ``request_id`` and ``user_id``
    when those are bound. Values passed explicitly via ``extra`` win: an attribute
    already present on the record is left untouched.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add the bound context attributes to the record and keep it.

        :param record: Record about to be handled.
        :return: Always ``True``; the record is never dropped.
        """
        if not hasattr(record, "request_id"):
            request_id = _request_id_var.get()
            if request_id is not None:
                record.request_id = request_id
        if not hasattr(record, "user_id"):
            user_id = _user_id_var.get()
            if user_id is not None:
                record.user_id = user_id
        return True
