"""Tests for the reduction of database error text."""

from types import SimpleNamespace

import psycopg2.errors
import pytest

from api.db.error_text import (
    database_error_chain,
    exception_chain,
    is_database_module,
    safe_error_text,
    safe_message_text,
)
from tests.shared.database_errors import (
    SENTINEL,
    bind_processor_error,
    psycopg2_invalid_uuid,
    psycopg2_unique_violation,
    psycopg3_unique_violation,
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
