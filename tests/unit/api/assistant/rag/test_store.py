"""Unit tests for store.py that need no database."""

import pytest

from api.assistant.rag.store import make_engine


def test_make_engine_refuses_an_empty_url():
    """
    GIVEN no ASSISTANT_VECTOR_DB_URL (the setting has no default)
    WHEN make_engine is called with the empty string
    THEN it raises ValueError naming the variable, before any connection attempt
    """
    # WHEN/THEN
    with pytest.raises(ValueError, match="ASSISTANT_VECTOR_DB_URL"):
        make_engine("")
