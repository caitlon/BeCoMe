"""Tests for the reduction of database error text."""

import logging
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import psycopg
import psycopg.errors
import psycopg2
import psycopg2.errors
import pytest

from api.db.error_text import (
    CONNECTION_FAILURE_LABELS,
    connection_failure_label,
    database_error_chain,
    exception_chain,
    format_exception_safely,
    is_database_module,
    safe_error_text,
    safe_message_text,
)
from api.logging_config import SafeTextFormatter
from tests.shared.database_errors import (
    SENTINEL,
    bind_processor_error,
    psycopg2_connection_refused,
    psycopg2_invalid_uuid,
    psycopg2_unique_violation,
    psycopg3_unique_violation,
    raised,
    wrap,
)


class _UniqueViolationWithDiagnostics(psycopg2.errors.UniqueViolation):
    """A driver error that reports a SQLSTATE and schema identifiers, as a live one does."""

    __module__ = "psycopg2.errors"
    pgcode = "23505"
    diag = SimpleNamespace(constraint_name="users_email_key", table_name="users", column_name=None)


class _BrokenStringError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("no text")


class TestIsDatabaseModule:
    """Which module names count as database code."""

    @pytest.mark.parametrize(
        "module",
        ["sqlalchemy.exc", "sqlalchemy", "psycopg2.errors", "psycopg.errors", "psycopg"],
    )
    def test_accepts_sqlalchemy_and_both_drivers(self, module):
        """
        GIVEN the module of a SQLAlchemy, psycopg2 or psycopg 3 error
        WHEN it is checked
        THEN it counts as a database module
        """
        assert is_database_module(module) is True

    @pytest.mark.parametrize("module", ["builtins", "api.exceptions", "mypsycopg", None, 3])
    def test_rejects_anything_else(self, module):
        """
        GIVEN a module name that is not SQLAlchemy or a driver, or not a string
        WHEN it is checked
        THEN it does not count
        """
        assert is_database_module(module) is False


class TestSafeMessageText:
    """First line, cut at the first quote mark."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ('invalid input syntax for type uuid: "x"', 'invalid input syntax for type uuid: "***'),
            ("Not a boolean value: 'a\"b'", "Not a boolean value: '***"),
            ("bad 'abc' and \"x y\"", "bad '***"),
        ],
        ids=["double", "single-holding-double", "single-first"],
    )
    def test_cuts_at_the_first_quote_mark_of_either_kind(self, text, expected):
        """
        GIVEN a first line with a quote mark of either kind
        WHEN it is reduced
        THEN the text before the earliest mark stays, then that mark and the mask
        AND everything after it is dropped
        """
        assert safe_message_text(text) == expected

    def test_a_line_without_a_quote_mark_is_unchanged(self):
        """
        GIVEN a first line with no quote mark
        WHEN it is reduced
        THEN it is returned as it is
        """
        assert safe_message_text("deadlock detected") == "deadlock detected"

    @pytest.mark.parametrize(
        "text",
        [
            f'invalid input syntax for type uuid: "ab"{SENTINEL}"',
            f'invalid input syntax for type uuid: "{SENTINEL}"x"',
            f"Not a boolean value: 'a'{SENTINEL}'",
            f'invalid input syntax for type uuid: "a\'{SENTINEL}"',
            f"Not a boolean value: 'a\"{SENTINEL}'",
            f'foo "ident" bar: "{SENTINEL}',
        ],
    )
    def test_a_quote_mark_inside_the_value_does_not_expose_its_rest(self, text):
        """
        GIVEN a quoted value that itself holds a quote mark (PostgreSQL does not escape it)
        WHEN the message is reduced
        THEN no part of the value survives
        """
        assert SENTINEL not in safe_message_text(text)

    def test_text_after_the_first_quote_mark_is_dropped_with_later_spans(self):
        """
        GIVEN a first line with two quoted identifiers and text after them
        WHEN it is reduced
        THEN the line is cut at the first mark and nothing after it is kept
        """
        text = 'null value in column "email" of relation "users" violates not-null constraint'

        assert safe_message_text(text) == 'null value in column "***'

    def test_keeps_only_the_first_line(self):
        """
        GIVEN a message with a DETAIL line
        WHEN it is reduced
        THEN the DETAIL line is gone
        """
        text = f"duplicate key\nDETAIL:  Key (email)=({SENTINEL}) already exists."

        assert safe_message_text(text) == "duplicate key"

    def test_masks_a_quoted_value_that_spans_lines(self):
        """
        GIVEN a quoted value that contains a line break
        WHEN the message is reduced
        THEN no part of the value survives
        """
        text = f'invalid input syntax for type integer: "{SENTINEL}\nsecond line"'

        assert safe_message_text(text) == 'invalid input syntax for type integer: "***'

    def test_empty_text_stays_empty(self):
        """
        GIVEN an empty message
        WHEN it is reduced
        THEN the result is an empty string
        """
        assert safe_message_text("") == ""


class TestSafeErrorText:
    """What may leave the process for one exception."""

    def test_wrapped_psycopg2_unique_violation_drops_detail_statement_and_value(self):
        """
        GIVEN SQLAlchemy's wrapper around a psycopg2 unique violation
        WHEN its text is reduced
        THEN the first line stays up to the first quote mark, then the mask
        AND neither the value nor the statement remains
        """
        wrapped, _ = psycopg2_unique_violation()

        text = safe_error_text(wrapped)

        assert text == (
            '(psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "***'
        )

    def test_type_error_quotes_are_masked(self):
        """
        GIVEN a driver error whose first line quotes the offending value
        WHEN its text is reduced
        THEN the value is masked
        """
        _, orig = psycopg2_invalid_uuid()

        assert safe_error_text(orig) == 'invalid input syntax for type uuid: "***'

    def test_psycopg2_sqlstate_and_schema_names_are_appended(self):
        """
        GIVEN a driver error that reports a SQLSTATE and constraint and table names
        WHEN its text is reduced
        THEN they follow the message, and the unset column is left out
        """
        orig = _UniqueViolationWithDiagnostics(f"clash\nDETAIL: Key (email)=({SENTINEL})")

        assert (
            safe_error_text(orig)
            == "clash (SQLSTATE 23505; constraint users_email_key; table users)"
        )

    def test_sqlstate_of_a_wrapped_driver_error_is_read_through_orig(self):
        """
        GIVEN SQLAlchemy's wrapper around a driver error that reports a SQLSTATE
        WHEN the wrapper's text is reduced
        THEN the SQLSTATE and the names of the driver error follow the first line
        """
        orig = _UniqueViolationWithDiagnostics("clash")
        wrapped, _ = psycopg2_unique_violation()
        wrapped.orig = orig

        assert safe_error_text(wrapped).endswith(
            "(SQLSTATE 23505; constraint users_email_key; table users)"
        )

    def test_psycopg3_sqlstate_is_appended(self):
        """
        GIVEN a psycopg 3 unique violation
        WHEN its text is reduced
        THEN the class-level SQLSTATE 23505 is reported
        """
        _, orig = psycopg3_unique_violation()

        text = safe_error_text(orig)

        assert text.endswith("(SQLSTATE 23505)")
        assert SENTINEL not in text

    def test_builtin_error_inside_a_statement_error_keeps_its_first_line_cut(self):
        """
        GIVEN a statement error around the TypeError of a bind processor
        WHEN the wrapper's text is reduced
        THEN the line is cut at the first quote mark and the statement is dropped
        """
        wrapped, _ = bind_processor_error()

        assert safe_error_text(wrapped) == "(builtins.TypeError) Not a boolean value: '***"

    def test_never_raises_for_a_broken_string_conversion(self):
        """
        GIVEN an exception whose ``__str__`` raises
        WHEN its text is reduced
        THEN the type name is returned
        """
        assert safe_error_text(_BrokenStringError()) == "_BrokenStringError"


class TestChains:
    """Which exceptions of a chain are reduced."""

    def test_exception_chain_follows_cause_and_context_once_each(self):
        """
        GIVEN a cause and a context that point back at the start
        WHEN the chain is walked
        THEN each exception appears once and the walk ends
        """
        first, second, third = ValueError("a"), KeyError("b"), RuntimeError("c")
        first.__cause__ = second
        first.__context__ = third
        second.__context__ = first

        assert exception_chain(first) == [first, second, third]

    def test_database_chain_holds_the_wrapper_and_the_driver_error(self):
        """
        GIVEN a wrapper raised from a driver error under an application error
        WHEN the chain to reduce is built
        THEN it holds both database errors and not the application error
        """
        wrapped, orig = psycopg2_unique_violation()
        top = RuntimeError("service failed")
        top.__cause__ = wrapped
        wrapped.__cause__ = orig

        assert database_error_chain(top) == [wrapped, orig]

    def test_database_chain_includes_a_builtin_orig_of_a_statement_error(self):
        """
        GIVEN a statement error around a builtin TypeError
        WHEN the chain to reduce is built
        THEN the TypeError is in it
        """
        wrapped, orig = bind_processor_error()

        assert orig in database_error_chain(wrapped)

    def test_database_chain_is_empty_without_a_database_error(self):
        """
        GIVEN a chain of application errors
        WHEN the chain to reduce is built
        THEN it is empty
        """
        top = ValueError("a")
        top.__cause__ = KeyError("b")

        assert database_error_chain(top) == []


class TestFormatExceptionSafely:
    """The traceback text for a log record."""

    def test_reduces_every_database_error_of_the_chain(self):
        """
        GIVEN a wrapper raised from a psycopg2 unique violation
        WHEN its traceback is formatted
        THEN both closing lines are reduced and the sentinel is gone
        AND the traceback keeps its frames and the cause separator
        """
        wrapped, orig = psycopg2_unique_violation()
        exc_info = raised(wrapped, orig)

        text = format_exception_safely(exc_info)

        assert text is not None
        assert SENTINEL not in text
        assert "DETAIL" not in text
        assert "INSERT INTO" not in text
        assert (
            'psycopg2.errors.UniqueViolation: duplicate key value violates unique constraint "***'
            in text
        )
        assert "sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation)" in text
        assert "The above exception was the direct cause of the following exception" in text
        assert "raise wrapped from cause" in text
        assert not text.endswith("\n")

    def test_prints_the_root_cause_before_the_wrapper(self):
        """
        GIVEN a wrapper raised from a driver error
        WHEN its traceback is formatted
        THEN the driver error comes first
        """
        wrapped, orig = psycopg2_invalid_uuid()

        text = format_exception_safely(raised(wrapped, orig))

        assert text is not None
        assert text.index("psycopg2.errors.InvalidTextRepresentation") < text.index(
            "sqlalchemy.exc.DataError"
        )

    def test_reduces_the_builtin_error_of_a_statement_error(self):
        """
        GIVEN a statement error raised from a TypeError that quotes a value
        WHEN its traceback is formatted
        THEN the value is masked and the builtin name is printed without a module
        """
        wrapped, orig = bind_processor_error()

        text = format_exception_safely(raised(wrapped, orig))

        assert text is not None
        assert SENTINEL not in text
        assert "TypeError: Not a boolean value: '***" in text
        assert "builtins.TypeError" not in text.replace("(builtins.TypeError)", "")

    def test_keeps_the_text_of_a_non_database_member_of_a_mixed_chain(self):
        """
        GIVEN an application error raised from a wrapper that was raised from a driver error
        WHEN the chain is formatted
        THEN the application error keeps its own message
        AND the database errors are reduced
        """
        wrapped, orig = psycopg2_unique_violation()
        try:
            try:
                raise orig
            except psycopg2.errors.UniqueViolation as cause:
                raise wrapped from cause
        except Exception as caught:
            try:
                raise ValueError("service failed for the signup") from caught
            except ValueError:
                exc_info = sys.exc_info()

        text = format_exception_safely(exc_info)

        assert text is not None
        assert "ValueError: service failed for the signup" in text
        assert SENTINEL not in text

    def test_uses_the_context_when_there_is_no_cause(self):
        """
        GIVEN a database error that was being handled when another error was raised
        WHEN the chain is formatted
        THEN the context separator joins them and the database error is reduced
        """
        _, orig = psycopg2_unique_violation()
        try:
            try:
                raise orig
            except psycopg2.errors.UniqueViolation:
                raise ValueError("while handling")  # noqa: B904
        except ValueError:
            exc_info = sys.exc_info()

        text = format_exception_safely(exc_info)

        assert text is not None
        assert "During handling of the above exception, another exception occurred" in text
        assert SENTINEL not in text

    def test_returns_none_without_a_database_error(self):
        """
        GIVEN a chain with no database error
        WHEN it is formatted
        THEN None is returned so that the caller keeps its default formatting
        """
        try:
            raise ValueError(SENTINEL)
        except ValueError:
            exc_info = sys.exc_info()

        assert format_exception_safely(exc_info) is None

    def test_returns_none_without_an_exception(self):
        """
        GIVEN a tuple without an exception
        WHEN it is formatted
        THEN None is returned
        """
        assert format_exception_safely((None, None, None)) is None

    def test_default_formatter_output_for_a_non_database_chain_is_unchanged(self):
        """
        GIVEN a non-database exception chain
        WHEN the project's formatter and the standard one format it
        THEN the texts are identical
        """
        try:
            try:
                raise KeyError(SENTINEL)
            except KeyError as cause:
                raise ValueError("outer") from cause
        except ValueError:
            exc_info = sys.exc_info()

        assert SafeTextFormatter().formatException(exc_info) == logging.Formatter().formatException(
            exc_info
        )

    def test_reduces_a_database_error_inside_an_exception_group(self):
        """
        GIVEN an exception group whose member is a statement error raised from a driver error
        WHEN its traceback is formatted
        THEN the group line and both database errors are printed, the database errors reduced
        AND the sentinel, the DETAIL line and the statement are gone
        """
        wrapped, orig = psycopg2_unique_violation()
        member = raised(wrapped, orig)[1]
        assert member is not None
        try:
            raise ExceptionGroup("batch failed", [member])
        except ExceptionGroup:
            exc_info = sys.exc_info()

        text = format_exception_safely(exc_info)

        assert text is not None
        assert "ExceptionGroup: batch failed (1 sub-exception)" in text
        assert "Sub-exception 1 of 1:" in text
        assert "sqlalchemy.exc.IntegrityError: (psycopg2.errors.UniqueViolation)" in text
        assert 'unique constraint "***' in text
        assert SENTINEL not in text
        assert "DETAIL" not in text
        assert "INSERT INTO" not in text

    def test_a_suppressed_context_is_not_printed(self):
        """
        GIVEN a database error raised ``from None`` while another one was being handled
        WHEN the chain is formatted
        THEN only the outer error is printed, reduced, under its own type
        AND the suppressed context and the separator that would join it are absent
        """
        _, first_orig = psycopg2_unique_violation()
        second, _ = psycopg2_unique_violation()
        try:
            try:
                raise first_orig
            except psycopg2.errors.UniqueViolation:
                raise second from None
        except Exception:
            exc_info = sys.exc_info()

        text = format_exception_safely(exc_info)

        assert text is not None
        assert SENTINEL not in text
        assert "During handling of the above exception" not in text
        assert "The above exception was the direct cause" not in text
        assert "psycopg2.errors.UniqueViolation: duplicate key" not in text
        assert text.splitlines()[-1].startswith("sqlalchemy.exc.IntegrityError: ")

    def test_default_formatting_is_kept_for_a_non_database_exception_group(self):
        """
        GIVEN exception groups with no database error, one member having its own cause
        WHEN they are formatted
        THEN no reduction applies
        AND the project's formatter prints the same text as the standard one
        """
        try:
            raise ExceptionGroup("batch", [ValueError(SENTINEL), KeyError("k")])
        except ExceptionGroup:
            plain = sys.exc_info()
        try:
            try:
                raise KeyError(SENTINEL)
            except KeyError as cause:
                member = ValueError("member")
                member.__cause__ = cause
                raise ExceptionGroup("batch", [member]) from None
        except ExceptionGroup:
            with_cause = sys.exc_info()

        for exc_info in (plain, with_cause):
            assert format_exception_safely(exc_info) is None
            assert SafeTextFormatter().formatException(
                exc_info
            ) == logging.Formatter().formatException(exc_info)


_LIBPQ = 'connection to server at "127.0.0.1", port 54199 failed: '
_PG_HBA = 'no pg_hba.conf entry for host "10.1.2.3", user "becomeuser", database "become", '
_SERVER = "\tThis probably means the server terminated abnormally\n"

# The psycopg2 texts and psycopg 3's refused text were captured on 2026-11-27 from psycopg2
# 2.9.13 (libpq 16) and psycopg 3.3.9 against fake servers on loopback; the other psycopg 3 texts
# add psycopg 3's ``connection failed: `` prefix to them (the form psycopg 3 printed for every
# server FATAL); the dns text and the OS-level reasons follow libpq's format strings.
_CONNECT_FAILURES = [
    ("refused", f"{_LIBPQ}Connection refused\n\tIs the server running on that host?\n"),
    ("timeout", f"{_LIBPQ}timeout expired\n"),
    ("timeout", f"{_LIBPQ}Connection timed out\n"),
    ("closed", f"{_LIBPQ}server closed the connection unexpectedly\n{_SERVER}"),
    ("closed", f"{_LIBPQ}Connection reset by peer\n"),
    ("unreachable", f"{_LIBPQ}Network is unreachable\n"),
    ("unreachable", f"{_LIBPQ}No route to host\n"),
    ("authentication", f'{_LIBPQ}FATAL:  password authentication failed for user "becomeuser"\n'),
    ("authentication", f"{_LIBPQ}FATAL:  {_PG_HBA}no encryption\n"),
    ("authentication", f"{_LIBPQ}FATAL:  {_PG_HBA}SSL encryption\n"),
    ("authentication", f'{_LIBPQ}FATAL:  role "becomeuser" does not exist\n'),
    (
        "authentication",
        'connection to server at "127.0.0.1", port 5432 failed: FATAL:  pg_hba.conf rejects '
        'connection for host "10.1.2.3", user "becomeuser", database "become", SSL encryption\n',
    ),
    (
        "refused",
        "could not connect to server: Connection refused\n"
        '\tIs the server running on host "db.internal" (10.0.0.5) and accepting\n'
        "\tTCP/IP connections on port 5432?\n",
    ),
    ("unknown_database", f'{_LIBPQ}FATAL:  database "become" does not exist\n'),
    ("too_many_connections", f"{_LIBPQ}FATAL:  sorry, too many clients already\n"),
    ("too_many_connections", f'{_LIBPQ}FATAL:  too many connections for role "becomeuser"\n'),
    (
        "too_many_connections",
        f"{_LIBPQ}FATAL:  remaining connection slots are reserved for roles with the SUPERUSER "
        "attribute\n",
    ),
    ("unavailable", f"{_LIBPQ}FATAL:  the database system is starting up\n"),
    ("unavailable", f"{_LIBPQ}FATAL:  the database system is shutting down\n"),
    ("unavailable", f"{_LIBPQ}FATAL:  terminating connection due to administrator command\n"),
    ("ssl", f"{_LIBPQ}server does not support SSL, but SSL was required\n"),
    ("ssl", f"{_LIBPQ}SSL error: wrong version number\nThis may indicate a protocol mismatch.\n"),
    ("ssl", f"{_LIBPQ}SSL connection has been closed unexpectedly\n"),
    ("dns", 'could not translate host name "db.internal" to address: Name or service not known\n'),
    ("dns", "failed to resolve host '127.0.0.1': [Errno 8] nodename nor servname provided\n"),
    ("other", f"{_LIBPQ}something new\n"),
]


def _psycopg2_error(text: str) -> BaseException:
    return psycopg2.OperationalError(text)


def _psycopg3_error(text: str) -> BaseException:
    return psycopg.OperationalError(f"connection failed: {text.rstrip()}")


def _wrapped_psycopg2_error(text: str) -> BaseException:
    return wrap(psycopg2.OperationalError(text), psycopg2.Error)


def _wrapped_psycopg3_error(text: str) -> BaseException:
    return wrap(_psycopg3_error(text), psycopg.Error)


_BUILDERS = [_psycopg2_error, _psycopg3_error, _wrapped_psycopg2_error, _wrapped_psycopg3_error]
_BUILDER_IDS = ["psycopg2", "psycopg3", "wrapped-psycopg2", "wrapped-psycopg3"]


class _ServerShutdown(psycopg2.OperationalError):
    """A server error that carries a SQLSTATE, as a live one does."""

    pgcode = "57P01"


class TestConnectionFailureLabel:
    """A failed connection keeps one fixed reason and nothing it names."""

    @pytest.mark.parametrize("build", _BUILDERS, ids=_BUILDER_IDS)
    @pytest.mark.parametrize(("label", "text"), _CONNECT_FAILURES)
    def test_every_known_reason_gets_its_label(self, build, label, text):
        """
        GIVEN the message of a failed connection, from either driver, raw or wrapped
        WHEN its label is read and its text reduced
        THEN the label is the reason and the reduced text ends with it
        AND the host and the port are gone from the reduced text
        """
        exc = build(text)

        assert label in CONNECTION_FAILURE_LABELS
        assert connection_failure_label(exc) == label
        reduced = safe_error_text(exc)
        assert reduced.endswith(f" (connection failure: {label})")
        assert "127.0.0.1" not in reduced
        assert "54199" not in reduced

    @pytest.mark.parametrize(
        ("label", "text"),
        [
            (
                "refused",
                'connection to server at "ssl-db.internal" (10.0.0.5), port 5 failed: '
                "Connection refused",
            ),
            (
                "authentication",
                f'{_LIBPQ}FATAL:  password authentication failed for user "timed out"',
            ),
            (
                "authentication",
                f'{_LIBPQ}FATAL:  password authentication failed for user "sslreader"',
            ),
            ("authentication", f'{_LIBPQ}FATAL:  role "timed out" does not exist'),
            ("unknown_database", f'{_LIBPQ}FATAL:  database "ssl" does not exist'),
            ("too_many_connections", f'{_LIBPQ}FATAL:  too many connections for role "refused"'),
            ("other", f'{_LIBPQ}something new "authentication failed'),
            ("other", f"{_LIBPQ}something new 'connection refused"),
        ],
    )
    def test_a_name_in_the_message_does_not_choose_the_label(self, label, text):
        """
        GIVEN a failed connection whose host, user, role or database name holds a reason word
            or whose text after an unclosed quote mark holds one
        WHEN its label is read
        THEN only the words outside the quote marks decide it
        """
        assert connection_failure_label(psycopg2.OperationalError(text)) == label

    @pytest.mark.parametrize(
        ("exc", "label"),
        [
            (psycopg.errors.ConnectionTimeout("connection timeout expired"), "timeout"),
            (
                psycopg.OperationalError(
                    f"connection failed: {_LIBPQ}Connection refused\n"
                    "Multiple connection attempts failed. All failures were:\n"
                    "- host: 'db.internal', port: '5432', hostaddr: '10.0.0.5': timeout expired\n"
                ),
                "refused",
            ),
            (
                psycopg.OperationalError(
                    'connection failed: connection to server at "127.0.0.1", port 54199 failed: '
                    "could not receive data from server: Connection refused"
                ),
                "refused",
            ),
        ],
        ids=["connection-timeout", "several-attempts", "refused"],
    )
    def test_psycopg3_only_errors_are_labelled(self, exc, label):
        """
        GIVEN psycopg 3's own timeout error, and its message after several failed attempts
        WHEN their labels are read
        THEN the timeout class is ``timeout`` and the last attempt on the first line decides
            the other
        AND the lines that name each host are gone from the reduced text
        """
        assert connection_failure_label(exc) == label
        assert "db.internal" not in safe_error_text(exc)

    @pytest.mark.parametrize(
        "exc",
        [
            _ServerShutdown(f"{_LIBPQ}FATAL:  terminating connection due to administrator command"),
            psycopg.errors.AdminShutdown("connection failed: terminating connection"),
            psycopg2.OperationalError("server closed the connection unexpectedly\n" + _SERVER),
            psycopg2.OperationalError("connection to server was lost\n"),
            psycopg2.ProgrammingError(f"{_LIBPQ}Connection refused"),
            ValueError(f"{_LIBPQ}Connection refused"),
        ],
        ids=[
            "psycopg2-sqlstate",
            "psycopg3-sqlstate",
            "mid-query",
            "connection-lost",
            "not-operational",
            "not-a-database-error",
        ],
    )
    def test_anything_but_a_connect_failure_has_no_label(self, exc):
        """
        GIVEN a server error with a SQLSTATE, a connection that dropped in the middle of a
            query, an error of another class, or an exception that is no database error
        WHEN its label is read
        THEN there is none
        """
        assert connection_failure_label(exc) is None
        assert "connection failure" not in safe_error_text(exc)

    def test_a_lost_connection_keeps_its_plain_text(self):
        """
        GIVEN libpq's ``connection to server was lost``, a mid-query error
        WHEN its text is reduced
        THEN it is the plain reduced text, with no label
        """
        exc = psycopg2.OperationalError("connection to server was lost\n")

        assert safe_error_text(exc) == safe_message_text(str(exc))

    def test_a_dropped_connection_keeps_its_plain_text(self):
        """
        GIVEN a connection that dropped in the middle of a query
        WHEN its text is reduced
        THEN it is the first line alone, as before the label existed
        """
        exc = psycopg2.OperationalError("server closed the connection unexpectedly\n" + _SERVER)

        assert safe_error_text(exc) == "server closed the connection unexpectedly"

    def test_the_label_is_found_through_the_sqlalchemy_wrapper_and_never_raises(self):
        """
        GIVEN a wrapper around a refused connection, and a driver error whose text cannot be read
        WHEN their labels are read
        THEN the wrapper has the label of its driver error and the broken one has none
        """
        wrapped, _ = psycopg2_connection_refused()

        class Broken(psycopg2.OperationalError):
            def __str__(self) -> str:
                raise RuntimeError("no text")

        assert connection_failure_label(wrapped) == "refused"
        assert connection_failure_label(Broken()) is None
        assert safe_error_text(Broken()) == "Broken"


_WITHOUT_PSYCOPG3 = """
import sys
sys.path.insert(0, sys.argv[1])
sys.modules["psycopg"] = None  # an import of psycopg 3 now raises ImportError
import psycopg2
from api.db.error_text import connection_failure_label

error = psycopg2.OperationalError('connection to server at "h", port 1 failed: Connection refused')
print(connection_failure_label(error))
"""


def test_the_module_works_without_psycopg3():
    """
    GIVEN an API image built without the ``assistant`` extra, where psycopg 3 is missing
    WHEN the module is imported and a refused psycopg2 connection is labelled
    THEN the import succeeds and the label is ``refused``
    """
    root = Path(__file__).resolve().parents[4]

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", "-c", _WITHOUT_PSYCOPG3, str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "refused"
