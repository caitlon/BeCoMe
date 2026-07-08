"""Every request DTO must reject unknown fields (extra='forbid')."""

import pytest
from pydantic import BaseModel, ValidationError

from api.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
)
from api.schemas.calculation import CalculateRequest, ExpertInput
from api.schemas.invitation import InviteByEmailRequest
from api.schemas.opinion import OpinionCreate
from api.schemas.project import ProjectCreate, ProjectUpdate, TransferOwnershipRequest

REQUEST_MODELS: list[type[BaseModel]] = [
    RegisterRequest,
    RefreshTokenRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ProjectCreate,
    ProjectUpdate,
    TransferOwnershipRequest,
    OpinionCreate,
    InviteByEmailRequest,
    ExpertInput,
    CalculateRequest,
]


@pytest.mark.parametrize("model", REQUEST_MODELS, ids=lambda m: m.__name__)
def test_request_dto_rejects_unknown_fields(model: type[BaseModel]) -> None:
    """An unexpected field raises an extra_forbidden error.

    Guards the API contract so typo'd or injected fields are rejected loudly
    instead of being silently dropped.
    """
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate({"unexpected_field": "x"})

    assert any(err["type"] == "extra_forbidden" for err in exc_info.value.errors())
