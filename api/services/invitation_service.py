"""Invitation business logic service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlmodel import Session, select

from api.db.models import Invitation, MemberRole, Project, ProjectMember, User


class InvitationNotFoundError(Exception):
    """Raised when invitation is not found."""


class InvitationExpiredError(Exception):
    """Raised when invitation has expired."""


class InvitationAlreadyUsedError(Exception):
    """Raised when invitation has already been used."""


class UserAlreadyMemberError(Exception):
    """Raised when user is already a member of the project."""


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone (handle SQLite naive datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class InvitationService:
    """Service for invitation-related operations."""

    DEFAULT_EXPIRATION_DAYS = 7

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        :param session: SQLModel session for database operations
        """
        self._session = session

    def create_invitation(
        self,
        project_id: UUID,
        expires_in_days: int | None = None,
    ) -> Invitation:
        """Create a new invitation for a project.

        :param project_id: ID of the project to invite to
        :param expires_in_days: Days until expiration (default: 7)
        :return: Created Invitation instance
        """
        if expires_in_days is None:
            expires_in_days = self.DEFAULT_EXPIRATION_DAYS

        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        invitation = Invitation(
            project_id=project_id,
            expires_at=expires_at,
        )
        self._session.add(invitation)
        self._session.commit()
        self._session.refresh(invitation)
        return invitation

    def get_invitation_by_token(self, token: UUID) -> Invitation | None:
        """Get invitation by its token.

        :param token: Invitation token (UUID)
        :return: Invitation if found, None otherwise
        """
        statement = select(Invitation).where(Invitation.token == token)
        return self._session.exec(statement).first()

    def get_invitation_with_project(self, token: UUID) -> tuple[Invitation, Project] | None:
        """Get invitation with its associated project.

        :param token: Invitation token
        :return: Tuple of (Invitation, Project) if found, None otherwise
        """
        statement = select(Invitation, Project).join(Project).where(Invitation.token == token)
        result = self._session.exec(statement).first()
        return result if result else None

    def get_invitation_details(self, token: UUID) -> tuple[Invitation, Project, User] | None:
        """Get invitation with project and admin details.

        :param token: Invitation token
        :return: Tuple of (Invitation, Project, Admin User) if found, None otherwise
        """
        statement = (
            select(Invitation, Project, User)
            .join(Project, Invitation.project_id == Project.id)  # type: ignore[arg-type]
            .join(User, Project.admin_id == User.id)  # type: ignore[arg-type]
            .where(Invitation.token == token)
        )
        result = self._session.exec(statement).first()
        return result if result else None

    def accept_invitation(self, token: UUID, user_id: UUID) -> ProjectMember:
        """Accept an invitation and add user to project.

        :param token: Invitation token
        :param user_id: ID of the user accepting the invitation
        :return: Created ProjectMember instance
        :raises InvitationNotFoundError: If invitation doesn't exist
        :raises InvitationExpiredError: If invitation has expired
        :raises InvitationAlreadyUsedError: If invitation was already used
        :raises UserAlreadyMemberError: If user is already a member
        """
        invitation = self.get_invitation_by_token(token)
        if not invitation:
            raise InvitationNotFoundError(f"Invitation with token {token} not found")

        if invitation.used_by_id is not None:
            raise InvitationAlreadyUsedError("Invitation has already been used")

        if datetime.now(UTC) > _ensure_utc(invitation.expires_at):
            raise InvitationExpiredError("Invitation has expired")

        # Check if user is already a member
        existing_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == invitation.project_id,
                ProjectMember.user_id == user_id,
            )
        ).first()

        if existing_membership:
            raise UserAlreadyMemberError(
                f"User {user_id} is already a member of project {invitation.project_id}"
            )

        # Mark invitation as used
        invitation.used_by_id = user_id
        self._session.add(invitation)

        # Add user as expert member
        membership = ProjectMember(
            project_id=invitation.project_id,
            user_id=user_id,
            role=MemberRole.EXPERT,
        )
        self._session.add(membership)
        self._session.commit()
        self._session.refresh(membership)
        return membership

    def is_invitation_valid(self, token: UUID) -> bool:
        """Check if invitation is valid (exists, not used, not expired).

        :param token: Invitation token
        :return: True if invitation is valid
        """
        invitation = self.get_invitation_by_token(token)
        if not invitation:
            return False
        if invitation.used_by_id is not None:
            return False
        return datetime.now(UTC) <= _ensure_utc(invitation.expires_at)
