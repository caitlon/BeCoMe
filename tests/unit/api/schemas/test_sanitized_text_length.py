"""Tests that a text field at its length cap keeps that length after sanitizing.

``&``, ``<`` and ``>`` used to leave the sanitizer as five- and four-character entities, so a
value that passed ``max_length`` came out longer than the database column.
"""

import pytest
from pydantic import ValidationError

from api.schemas.opinion import OPINION_POSITION_MAX, OpinionCreate
from api.schemas.project import (
    PROJECT_DESCRIPTION_MAX,
    PROJECT_NAME_MAX,
    PROJECT_SCALE_UNIT_MAX,
    ProjectCreate,
    ProjectUpdate,
)

_FUZZY = {"lower_bound": 1.0, "peak": 2.0, "upper_bound": 3.0}

# (schema, field, cap, extra fields the schema needs)
_FIELDS = [
    (ProjectCreate, "name", PROJECT_NAME_MAX, {}),
    (ProjectCreate, "description", PROJECT_DESCRIPTION_MAX, {"name": "P"}),
    (ProjectCreate, "scale_unit", PROJECT_SCALE_UNIT_MAX, {"name": "P"}),
    (ProjectUpdate, "name", PROJECT_NAME_MAX, {}),
    (ProjectUpdate, "description", PROJECT_DESCRIPTION_MAX, {}),
    (ProjectUpdate, "scale_unit", PROJECT_SCALE_UNIT_MAX, {}),
    (OpinionCreate, "position", OPINION_POSITION_MAX, _FUZZY),
]
_IDS = [f"{schema.__name__}.{field}" for schema, field, _, _ in _FIELDS]


@pytest.mark.parametrize(("schema", "field", "cap", "extra"), _FIELDS, ids=_IDS)
@pytest.mark.parametrize("char", ["&", "<", ">"])
class TestTextAtItsCap:
    """A text field made of special characters keeps its length through sanitizing."""

    def test_value_at_the_cap_is_accepted_unchanged(self, schema, field, cap, extra, char):
        """
        GIVEN a value of exactly the field's cap made of one special character
        WHEN the schema is built
        THEN the value is accepted and comes out equal to the input
        """
        # WHEN
        model = schema(**{**extra, field: char * cap})

        # THEN
        value = getattr(model, field)
        assert len(value) == cap
        assert value == char * cap

    def test_value_over_the_cap_is_refused(self, schema, field, cap, extra, char):
        """
        GIVEN a value one character over the field's cap
        WHEN the schema is built
        THEN ValidationError is raised
        """
        # WHEN / THEN
        with pytest.raises(ValidationError):
            schema(**{**extra, field: char * (cap + 1)})
