"""Invitation management routes for email-based invitations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth.dependencies import CurrentUser
from api.dependencies import ProjectAdmin, get_invitation_service
from api.exceptions import AlreadyInvitedError, UserNotFoundForInvitationError
from api.schemas.invitation import (
    InvitationListItemResponse,
    InvitationResponse,
    InviteByEmailRequest,
)
from api.schemas.project import MemberResponse
from api.services.invitation_service import InvitationService

router = APIRouter(prefix="/api/v1", tags=["invitations"])


@router.post(
    "/projects/{project_id}/invite",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite user by email",
)
def invite_by_email(
    project: ProjectAdmin,
    request: InviteByEmailRequest,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> InvitationResponse:
    """Invite a registered user to a project by email. Only admin can invite.

    :param project: Project (verified admin)
    :param request: Email of user to invite
    :param current_user: Authenticated admin user
    :param invitation_service: Invitation service
    :return: Created invitation
    :raises HTTPException: 404 if user not found, 409 if already member or invited
    """
    try:
        invitation, invitee = invitation_service.invite_by_email(
            project_id=project.id,
            inviter_id=current_user.id,
            invitee_email=request.email,
        )
    except UserNotFoundForInvitationError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with this email",
        ) from err
    except AlreadyInvitedError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a pending invitation",
        ) from err

    return InvitationResponse.from_model(invitation, invitee)


@router.get(
    "/invitations",
    response_model=list[InvitationListItemResponse],
    summary="List my invitations",
)
def list_my_invitations(
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> list[InvitationListItemResponse]:
    """Get all pending invitations for the current user.

    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :return: List of pending invitations with project details
    """
    invitations = invitation_service.get_user_invitations(current_user.id)
    return [
        InvitationListItemResponse.from_model(
            item.invitation,
            item.project,
            item.inviter,
            item.member_count,
        )
        for item in invitations
    ]


@router.post(
    "/invitations/{invitation_id}/accept",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Accept invitation",
)
def accept_invitation(
    invitation_id: UUID,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> MemberResponse:
    """Accept an invitation and join the project as expert.

    :param invitation_id: Invitation UUID
    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :return: Created membership details
    :raises HTTPException: 404 if invitation not found or not for this user
    """
    membership = invitation_service.accept_invitation(invitation_id, current_user.id)

    return MemberResponse(
        user_id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=membership.role.value,
        joined_at=membership.joined_at,
    )


@router.post(
    "/invitations/{invitation_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Decline invitation",
)
def decline_invitation(
    invitation_id: UUID,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> None:
    """Decline an invitation.

    :param invitation_id: Invitation UUID
    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :raises HTTPException: 404 if invitation not found or not for this user
    """
    invitation_service.decline_invitation(invitation_id, current_user.id)
