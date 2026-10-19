"""Invitation management routes for email-based invitations."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from api.auth.dependencies import CurrentUser
from api.auth.logging import hash_email
from api.dependencies import ProjectAdmin, get_invitation_service
from api.exceptions import (
    AlreadyInvitedError,
    ExampleProjectInvitationError,
    UserNotFoundForInvitationError,
)
from api.middleware.rate_limit import LIMIT_WRITE, limiter
from api.pagination import PaginationParams
from api.schemas.invitation import (
    InvitationListItemResponse,
    InvitationResponse,
    InviteByEmailRequest,
    ProjectInvitationResponse,
)
from api.schemas.project import MemberResponse
from api.services.invitation_service import InvitationService

logger = logging.getLogger("api.route.invitations")

router = APIRouter(prefix="/api/v1", tags=["invitations"])


def _log_invitation_rejected(reason: str, project_id: UUID, inviter_id: UUID, email: str) -> None:
    """Record an invitation the endpoint refused.

    The route catches each refusal only to call this, then re-raises it for
    ``become_api_error_handler``, which builds the response and its code. The handler logs
    the exception type but not the reason, project or inviter recorded here.

    The address is tagged, never written out: this endpoint is the application's
    email-enumeration surface, and a log of the addresses people probed for would be
    the registry the uniform rate limit exists to deny.

    :param reason: ``example_project``, ``invitee_not_found`` or ``already_invited``.
    :param project_id: Project the invitation targeted.
    :param inviter_id: Admin who sent it.
    :param email: Address that was invited.
    """
    logger.warning(
        "Invitation rejected",
        extra={
            "event": "invitation_rejected",
            "reason": reason,
            "project_id": str(project_id),
            "inviter_id": str(inviter_id),
            "email_hash": hash_email(email),
        },
    )


@router.post(
    "/projects/{project_id}/invite",
    status_code=status.HTTP_201_CREATED,
    summary="Invite user by email",
)
@limiter.limit(LIMIT_WRITE)
def invite_by_email(
    request: Request,
    project_id: UUID,
    project: ProjectAdmin,
    data: InviteByEmailRequest,
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
) -> InvitationResponse:
    """Invite a registered user to a project by email. Only admin can invite.

    Rate limited so the endpoint cannot be used to enumerate registered emails at speed.

    :param request: FastAPI request (for rate limiting)
    :param project: Project (verified admin)
    :param data: Email of user to invite
    :param current_user: Authenticated admin user
    :param invitation_service: Invitation service
    :return: Created invitation
    :raises UserNotFoundForInvitationError: If no user has this email (404)
    :raises UserAlreadyMemberError: If the user is already a member (409)
    :raises AlreadyInvitedError: If the user already has a pending invitation (409)
    :raises ExampleProjectInvitationError: If the project is the seeded example (409)
    """
    try:
        invitation, invitee = invitation_service.invite_by_email(
            project=project,
            inviter_id=current_user.id,
            invitee_email=data.email,
        )
    except ExampleProjectInvitationError:
        _log_invitation_rejected("example_project", project.id, current_user.id, data.email)
        raise
    except UserNotFoundForInvitationError:
        _log_invitation_rejected("invitee_not_found", project.id, current_user.id, data.email)
        raise
    except AlreadyInvitedError:
        _log_invitation_rejected("already_invited", project.id, current_user.id, data.email)
        raise

    return InvitationResponse.from_model(invitation, invitee)


@router.get(
    "/projects/{project_id}/invitations",
    summary="List pending invitations for a project",
)
def list_project_invitations(
    project_id: UUID,
    project: ProjectAdmin,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[ProjectInvitationResponse]:
    """Get pending invitations for a project. Accessible to the project admin only.

    :param project: Project (verified admin access)
    :param invitation_service: Invitation service
    :param pagination: Bounded limit/offset (capped at MAX_PAGE_SIZE)
    :return: List of pending invitations with invitee details
    """
    invitations = invitation_service.get_project_invitations(
        project.id, limit=pagination.limit, offset=pagination.offset
    )
    logger.debug(
        "Project invitations listed",
        extra={
            "event": "invitations_listed",
            "scope": "project",
            "project_id": str(project.id),
            "row_count": len(invitations),
        },
    )
    return [ProjectInvitationResponse.from_model(inv, invitee) for inv, invitee in invitations]


@router.get("/invitations", summary="List my invitations")
def list_my_invitations(
    current_user: CurrentUser,
    invitation_service: Annotated[InvitationService, Depends(get_invitation_service)],
    pagination: Annotated[PaginationParams, Depends()],
) -> list[InvitationListItemResponse]:
    """Get pending invitations for the current user.

    :param current_user: Authenticated user
    :param invitation_service: Invitation service
    :param pagination: Bounded limit/offset (capped at MAX_PAGE_SIZE)
    :return: List of pending invitations with project details
    """
    invitations = invitation_service.get_user_invitations(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    logger.debug(
        "User invitations listed",
        extra={
            "event": "invitations_listed",
            "scope": "user",
            "row_count": len(invitations),
        },
    )
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
    :raises InvitationNotFoundError: If the invitation does not exist or is not for this user
    :raises ExampleProjectInvitationError: If the invitation is into the seeded example
    :raises UserAlreadyMemberError: If the user is already a member of the project
    """
    membership = invitation_service.accept_invitation(invitation_id, current_user.id)

    return MemberResponse.from_model(membership, current_user, show_email=True)


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
    :raises InvitationNotFoundError: If the invitation does not exist or is not for this user
    """
    invitation_service.decline_invitation(invitation_id, current_user.id)
