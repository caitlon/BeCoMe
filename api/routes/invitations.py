"""Invitation management routes."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.auth.dependencies import CurrentUser
from api.dependencies import get_session
from api.schemas import InvitationCreate, InvitationInfoResponse, InvitationResponse, MemberResponse
from api.services.invitation_service import (
    InvitationAlreadyUsedError,
    InvitationExpiredError,
    InvitationNotFoundError,
    InvitationService,
    UserAlreadyMemberError,
    ensure_utc,
)
from api.services.project_service import ProjectService

router = APIRouter(prefix="/api/v1", tags=["invitations"])


def _get_invitation_service(session: Annotated[Session, Depends(get_session)]) -> InvitationService:
    """Dependency to get InvitationService instance."""
    return InvitationService(session)


def _get_project_service(session: Annotated[Session, Depends(get_session)]) -> ProjectService:
    """Dependency to get ProjectService instance."""
    return ProjectService(session)


@router.post(
    "/projects/{project_id}/invite",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project invitation",
)
def create_invitation(
    project_id: UUID,
    request: InvitationCreate,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(_get_invitation_service)],
    project_service: Annotated[ProjectService, Depends(_get_project_service)],
) -> InvitationResponse:
    """Create an invitation link for a project. Only admin can create invitations.

    :param project_id: Project UUID
    :param request: Invitation creation data
    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :param project_service: Project service
    :return: Created invitation with token
    :raises HTTPException: 404 if not found, 403 if not admin
    """
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if not project_service.is_admin(project_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only project admin can create invitations",
        )

    invitation = invitation_service.create_invitation(
        project_id=project_id,
        expires_in_days=request.expires_in_days,
    )

    return InvitationResponse(
        token=str(invitation.token),
        expires_at=invitation.expires_at,
        project_id=str(project.id),
        project_name=project.name,
    )


@router.get(
    "/invitations/{token}",
    response_model=InvitationInfoResponse,
    summary="Get invitation info",
)
def get_invitation_info(
    token: UUID,
    invitation_service: Annotated[InvitationService, Depends(_get_invitation_service)],
) -> InvitationInfoResponse:
    """Get public information about an invitation. No authentication required.

    :param token: Invitation token (UUID)
    :param invitation_service: Invitation service
    :return: Invitation details
    :raises HTTPException: 404 if invitation not found
    """
    result = invitation_service.get_invitation_details(token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    invitation, project, admin = result

    expires_at = ensure_utc(invitation.expires_at)
    is_valid = invitation.used_by_id is None and datetime.now(UTC) <= expires_at

    admin_name = admin.first_name
    if admin.last_name:
        admin_name = f"{admin.first_name} {admin.last_name}"

    return InvitationInfoResponse(
        project_name=project.name,
        project_description=project.description,
        admin_name=admin_name,
        expires_at=expires_at,
        is_valid=is_valid,
    )


@router.post(
    "/invitations/{token}/accept",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Accept invitation",
)
def accept_invitation(
    token: UUID,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(_get_invitation_service)],
) -> MemberResponse:
    """Accept an invitation and join the project as expert.

    :param token: Invitation token (UUID)
    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :return: Created membership details
    :raises HTTPException: 404 if not found, 400 if invalid/expired/used, 409 if already member
    """
    try:
        membership = invitation_service.accept_invitation(token, current_user.id)
    except InvitationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        ) from e
    except InvitationExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has expired",
        ) from e
    except InvitationAlreadyUsedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation has already been used",
        ) from e
    except UserAlreadyMemberError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this project",
        ) from e

    return MemberResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=membership.role.value,
        joined_at=membership.joined_at,
    )
