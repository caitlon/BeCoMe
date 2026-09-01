"""Invitation business logic service for email-based invitations."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlmodel import col, select

from api.db.models import Invitation, MemberRole, Project, ProjectMember, User
from api.exceptions import (
    AlreadyInvitedError,
    ExampleProjectInvitationError,
    InvitationNotFoundError,
    UserAlreadyMemberError,
    UserNotFoundForInvitationError,
)
from api.services.base import BaseService
from api.services.query_helpers import MemberCountSubquery, select_account_by_email

logger = logging.getLogger("api.service.invitation")


@dataclass(frozen=True)
class InvitationWithDetails:
    """Invitation with project, inviter, and member count."""

    invitation: Invitation
    project: Project
    inviter: User
    member_count: int


class InvitationService(BaseService):
    """Service for email-based invitation operations."""

    def invite_by_email(
        self,
        project: Project,
        inviter_id: UUID,
        invitee_email: str,
    ) -> tuple[Invitation, User]:
        """Invite a registered user to a project by email.

        Takes the project rather than its id because the caller has already loaded it to
        authorise the request, and because the example-project rule below needs the row
        itself. Fetching it again here would be a wasted query and a dependency the
        signature does not admit to.

        :param project: Project to invite to, already loaded by the caller
        :param inviter_id: ID of the user sending the invitation
        :param invitee_email: Email of the user to invite
        :return: Tuple of (created Invitation, invitee User)
        :raises ExampleProjectInvitationError: If the project is the seeded example
        :raises UserNotFoundForInvitationError: If no user with this email exists
        :raises UserAlreadyMemberError: If user is already a project member
        :raises AlreadyInvitedError: If user already has a pending invitation
        """
        # Checked here rather than in the route so the rule holds for every caller. The
        # example project ships with its thirteen opinions already in place and exists to
        # be read, so a fourteenth expert has nothing to contribute to it.
        if project.is_example:
            raise ExampleProjectInvitationError("The example project cannot take invitations")

        invitee = self._session.exec(select_account_by_email(invitee_email)).first()
        if not invitee:
            raise UserNotFoundForInvitationError(f"No user found with email {invitee_email}")

        existing_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == invitee.id,
            )
        ).first()
        if existing_membership:
            raise UserAlreadyMemberError("User is already a member of this project")

        existing_invitation = self._session.exec(
            select(Invitation).where(
                Invitation.project_id == project.id,
                Invitation.invitee_id == invitee.id,
            )
        ).first()
        if existing_invitation:
            raise AlreadyInvitedError("User already has a pending invitation")

        invitation = Invitation(
            project_id=project.id,
            invitee_id=invitee.id,
            inviter_id=inviter_id,
        )
        saved = self._save_and_refresh(invitation)
        logger.info(
            "Invitation created",
            extra={
                "event": "invitation_created",
                "invitation_id": str(saved.id),
                "project_id": str(project.id),
                "inviter_id": str(inviter_id),
                "invitee_id": str(saved.invitee_id),
            },
        )
        return saved, invitee

    def get_user_invitations(
        self, user_id: UUID, limit: int | None = None, offset: int = 0
    ) -> list[InvitationWithDetails]:
        """Get pending invitations for a user.

        :param user_id: ID of the user
        :param limit: Max rows to return; ``None`` returns every invitation.
        :param offset: Rows to skip when a limit is set.
        :return: List of invitations with project and inviter details
        """
        member_count_subquery = MemberCountSubquery.build()

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
        if limit is not None:
            statement = statement.limit(limit).offset(offset)

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
        if not invitation or invitation.invitee_id != user_id:
            raise InvitationNotFoundError("Invitation not found")

        existing_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == invitation.project_id,
                ProjectMember.user_id == user_id,
            )
        ).first()
        if existing_membership:
            self._delete_and_commit(invitation)
            raise UserAlreadyMemberError("User is already a member of this project")

        project_id = invitation.project_id
        inviter_id = invitation.inviter_id
        membership = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=MemberRole.EXPERT,
        )
        self._session.add(membership)
        self._session.delete(invitation)
        self._session.commit()
        self._session.refresh(membership)
        logger.info(
            "Invitation accepted",
            extra={
                "event": "invitation_accepted",
                "invitation_id": str(invitation_id),
                "project_id": str(project_id),
                "inviter_id": str(inviter_id),
                "user_id": str(user_id),
            },
        )
        return membership

    def get_project_invitations(
        self, project_id: UUID, limit: int | None = None, offset: int = 0
    ) -> list[tuple[Invitation, User]]:
        """Get pending invitations for a project with invitee details.

        :param project_id: Project UUID
        :param limit: Max rows to return; ``None`` returns every invitation.
        :param offset: Rows to skip when a limit is set.
        :return: List of (invitation, invitee) tuples ordered by creation date
        """
        statement = (
            select(Invitation, User)
            .join(User, Invitation.invitee_id == User.id)  # type: ignore[arg-type]
            .where(Invitation.project_id == project_id)
            .order_by(col(Invitation.created_at))
        )
        if limit is not None:
            statement = statement.limit(limit).offset(offset)
        return list(self._session.exec(statement).all())

    def decline_invitation(self, invitation_id: UUID, user_id: UUID) -> None:
        """Decline an invitation.

        :param invitation_id: Invitation ID
        :param user_id: ID of the user declining
        :raises InvitationNotFoundError: If invitation doesn't exist or not for this user
        """
        invitation = self.get_invitation_by_id(invitation_id)
        if not invitation or invitation.invitee_id != user_id:
            raise InvitationNotFoundError("Invitation not found")

        project_id = invitation.project_id
        inviter_id = invitation.inviter_id
        self._delete_and_commit(invitation)
        logger.info(
            "Invitation declined",
            extra={
                "event": "invitation_declined",
                "invitation_id": str(invitation_id),
                "project_id": str(project_id),
                "inviter_id": str(inviter_id),
                "user_id": str(user_id),
            },
        )
