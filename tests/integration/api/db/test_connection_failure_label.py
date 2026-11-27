"""The wording of the installed libpq and drivers still maps to a connection failure label.

A unit test cannot open a connection, so the connects to a closed loopback port live here.
Nothing listens on the port, so no server is needed and nothing leaves the machine.
"""

import socket
from collections.abc import Callable
from typing import Any

import psycopg
import psycopg2
import pytest

from api.db.error_text import connection_failure_label, safe_error_text


def _unused_loopback_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.mark.parametrize(
    ("connect", "error"),
    [(psycopg2.connect, psycopg2.OperationalError), (psycopg.connect, psycopg.OperationalError)],
    ids=["psycopg2", "psycopg3"],
)
def test_a_refused_loopback_connection_is_labelled_refused(
    connect: Callable[..., Any], error: type[Exception]
):
    """
    GIVEN a loopback port that nothing listens on
    WHEN a driver connects to it
    THEN the error has the label ``refused`` and the reduced text names no port
    """
    port = _unused_loopback_port()

    with pytest.raises(error) as caught:
        connect(host="127.0.0.1", port=port, dbname="x", user="u", connect_timeout=2)

    assert connection_failure_label(caught.value) == "refused"
    assert str(port) not in safe_error_text(caught.value)
