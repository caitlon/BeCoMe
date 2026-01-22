"""Invitation business logic service for email-based invitations."""

from dataclasses import dataclass
from uuid import UUID

from sqlmodel import Session, col, func, select

from api.db.models import Invitation, MemberRole, Project, ProjectMember, User
from api.exceptions import (
    InvitationNotFoundError,
    UserAlreadyMemberError,
)
from api.services.base import BaseService


class UserNotFoundError(Exception):
    """Raised when user with specified email is not found."""


class AlreadyInvitedError(Exception):
    """Raised when user already has a pending invitation."""


@dataclass(frozen=True)
class InvitationWithDetails:
    """Invitation with project, inviter, and member count."""

    invitation: Invitation
    project: Project
    inviter: User
    member_count: int


class InvitationService(BaseService):
    """Service for email-based invitation operations."""

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        :param session: SQLModel session for database operations
        """
        super().__init__(session)

    def invite_by_email(
        self,
        project_id: UUID,
        inviter_id: UUID,
        invitee_email: str,
    ) -> tuple[Invitation, User]:
        """Invite a registered user to a project by email.

        :param project_id: ID of the project to invite to
        :param inviter_id: ID of the user sending the invitation
        :param invitee_email: Email of the user to invite
        :return: Tuple of (created Invitation, invitee User)
        :raises UserNotFoundError: If no user with this email exists
        :raises UserAlreadyMemberError: If user is already a project member
        :raises AlreadyInvitedError: If user already has a pending invitation
        """
        # Find user by email (case-insensitive)
        invitee = self._session.exec(
            select(User).where(User.email == invitee_email.lower())
        ).first()
        if not invitee:
            raise UserNotFoundError(f"No user found with email {invitee_email}")

        # Check if user is already a member
        existing_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == invitee.id,
            )
        ).first()
        if existing_membership:
            raise UserAlreadyMemberError("User is already a member of this project")

        # Check if user already has a pending invitation
        existing_invitation = self._session.exec(
            select(Invitation).where(
                Invitation.project_id == project_id,
                Invitation.invitee_id == invitee.id,
            )
        ).first()
        if existing_invitation:
            raise AlreadyInvitedError("User already has a pending invitation")

        # Create invitation
        invitation = Invitation(
            project_id=project_id,
            invitee_id=invitee.id,
            inviter_id=inviter_id,
        )
        self._session.add(invitation)
        self._session.commit()
        self._session.refresh(invitation)
        return invitation, invitee

    def get_user_invitations(self, user_id: UUID) -> list[InvitationWithDetails]:
        """Get all pending invitations for a user.

        :param user_id: ID of the user
        :return: List of invitations with project and inviter details
        """
        # Subquery for member counts
        member_count_subquery = (
            select(ProjectMember.project_id, func.count().label("member_count"))
            .group_by(col(ProjectMember.project_id))
            .subquery()
        )

        statement = (
            select(Invitation, Project, User, member_count_subquery.c.member_count)
            .join(Project, Invitation.project_id == Project.id)  # type: ignore[arg-type]
            .join(User, Invitation.inviter_id == User.id)  # type: ignore[arg-type]
            .join(
                member_count_subquery,
                member_count_subquery.c.project_id == Project.id,
            )
            .where(Invitation.invitee_id == user_id)
            .order_by(col(Invitation.created_at).desc())
        )

        results = self._session.exec(statement).all()
        return [
            InvitationWithDetails(
                invitation=invitation,
                project=project,
                inviter=inviter,
                member_count=count,
            )
            for invitation, project, inviter, count in results
        ]

    def get_invitation_by_id(self, invitation_id: UUID) -> Invitation | None:
        """Get invitation by ID.

        :param invitation_id: Invitation UUID
        :return: Invitation if found, None otherwise
        """
        return self._session.get(Invitation, invitation_id)

    def accept_invitation(self, invitation_id: UUID, user_id: UUID) -> ProjectMember:
        """Accept an invitation and add user to project.

        :param invitation_id: Invitation ID
        :param user_id: ID of the user accepting
        :return: Created ProjectMember instance
        :raises InvitationNotFoundError: If invitation doesn't exist or is not for this user
        :raises UserAlreadyMemberError: If user is already a member
        """
        invitation = self.get_invitation_by_id(invitation_id)
        if not invitation:
            raise InvitationNotFoundError("Invitation not found")

        if invitation.invitee_id != user_id:
            raise InvitationNotFoundError("Invitation not found")

        # Check if user is already a member (edge case: added by another path)
        existing_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == invitation.project_id,
                ProjectMember.user_id == user_id,
            )
        ).first()
        if existing_membership:
            # Delete the invitation since user is already a member
            self._session.delete(invitation)
            self._session.commit()
            raise UserAlreadyMemberError("User is already a member of this project")

        # Add user as expert member
        membership = ProjectMember(
            project_id=invitation.project_id,
            user_id=user_id,
            role=MemberRole.EXPERT,
        )
        self._session.add(membership)

        # Delete the invitation
        self._session.delete(invitation)
        self._session.commit()
        self._session.refresh(membership)
        return membership

    def decline_invitation(self, invitation_id: UUID, user_id: UUID) -> None:
        """Decline an invitation.

        :param invitation_id: Invitation ID
        :param user_id: ID of the user declining
        :raises InvitationNotFoundError: If invitation doesn't exist or not for this user
        """
        invitation = self.get_invitation_by_id(invitation_id)
        if not invitation:
            raise InvitationNotFoundError("Invitation not found")

        if invitation.invitee_id != user_id:
            raise InvitationNotFoundError("Invitation not found")

        self._session.delete(invitation)
        self._session.commit()
