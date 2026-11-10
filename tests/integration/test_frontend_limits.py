"""Regression tests for form limits that the frontend mirrors from the API.

The create-project form validates the description length in the browser before
the request is sent. That limit is a hand-copied number in
frontend/src/components/modals/CreateProjectModal.tsx, and nothing ties it to
the max_length of the API schema, so the two drifted once (form 1000, API 2000)
and the form refused input the API accepts. This module reads the constant from
the TypeScript file as text and compares it with the field metadata of the
schemas, which are the source of truth.
"""

import re
from pathlib import Path

import pytest
from annotated_types import MaxLen

from api.schemas.project import ProjectCreate, ProjectUpdate

CREATE_PROJECT_MODAL_TS = (
    Path(__file__).parent.parent.parent
    / "frontend"
    / "src"
    / "components"
    / "modals"
    / "CreateProjectModal.tsx"
)
DESCRIPTION_MAX_LENGTH_PATTERN = re.compile(r"\bDESCRIPTION_MAX_LENGTH\s*=\s*(\d+)\b")


def _frontend_description_max_length() -> int:
    """Read DESCRIPTION_MAX_LENGTH out of CreateProjectModal.tsx.

    :return: The number the form validates the description against.
    :raises AssertionError: If the constant is missing or renamed, so the pin cannot go
        quiet.
    """
    match = DESCRIPTION_MAX_LENGTH_PATTERN.search(CREATE_PROJECT_MODAL_TS.read_text())
    assert match is not None, (
        f"DESCRIPTION_MAX_LENGTH = <n> not found in {CREATE_PROJECT_MODAL_TS}; "
        "update this test if the constant was renamed or moved"
    )
    return int(match.group(1))


def _schema_max_length(model: type[ProjectCreate] | type[ProjectUpdate]) -> int:
    """Read the max_length of the description field from the schema metadata.

    :param model: The request schema to inspect.
    :return: The maximum length the schema accepts for the description.
    """
    limits = [
        m.max_length for m in model.model_fields["description"].metadata if isinstance(m, MaxLen)
    ]
    assert len(limits) == 1, f"{model.__name__}.description has no single max_length: {limits}"
    return limits[0]


@pytest.mark.parametrize("model", [ProjectCreate, ProjectUpdate])
def test_create_project_form_description_limit_matches_api_schema(
    model: type[ProjectCreate] | type[ProjectUpdate],
) -> None:
    """The form's description limit equals the API schema's max_length."""
    assert _frontend_description_max_length() == _schema_max_length(model)
