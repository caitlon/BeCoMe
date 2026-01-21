"""Invitation management routes.

Exception handling follows OCP: all exceptions are handled
by centralized middleware, routes focus on business logic only.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.dependencies import ProjectAdmin, get_invitation_service
from api.schemas import (
    InvitationCreate,
    InvitationInfoResponse,
    InvitationResponse,
    MemberResponse,
)
from api.services.invitation_service import InvitationService

router = APIRouter(prefix="/api/v1", tags=["invitations"])


@router.post(
    "/projects/{project_id}/invite",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project invitation",
)
def create_invitation(
    project: ProjectAdmin,
    request: InvitationCreate,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> InvitationResponse:
    """Create an invitation link for a project. Only admin can create invitations.

    :param project: Project (verified admin)
    :param request: Invitation creation data
    :param invitation_service: Invitation service
    :return: Created invitation with token
    """
    invitation = invitation_service.create_invitation(
        project_id=project.id,
        expires_in_days=request.expires_in_days,
    )

    return InvitationResponse.from_model(invitation, project)


@router.get(
    "/invitations/{token}",
    response_model=InvitationInfoResponse,
    summary="Get invitation info",
)
def get_invitation_info(
    token: UUID,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
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
    return InvitationInfoResponse.from_model(invitation, project, admin)


@router.post(
    "/invitations/{token}/accept",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Accept invitation",
)
def accept_invitation(
    token: UUID,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> MemberResponse:
    """Accept an invitation and join the project as expert.

    All invitation exceptions (NotFound, Expired, AlreadyUsed, UserAlreadyMember)
    are handled by centralized exception middleware.

    :param token: Invitation token (UUID)
    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :return: Created membership details
    """
    membership = invitation_service.accept_invitation(token, current_user.id)

    return MemberResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=membership.role.value,
        joined_at=membership.joined_at,
    )
