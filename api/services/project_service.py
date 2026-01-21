"""Project business logic service."""

from uuid import UUID

from sqlmodel import Session, col, func, select

from api.db.models import MemberRole, Project, ProjectMember, User
from api.exceptions import MemberNotFoundError, ProjectNotFoundError, ScaleRangeError
from api.schemas import ProjectCreate, ProjectUpdate


class ProjectService:
    """Service for project-related operations."""

    def __init__(self, session: Session) -> None:
        """Initialize with database session.

        :param session: SQLModel session for database operations
        """
        self._session = session

    def create_project(self, user_id: UUID, data: ProjectCreate) -> Project:
        """Create a new project and add creator as admin.

        :param user_id: ID of the user creating the project
        :param data: Project creation data
        :return: Created Project instance
        """
        project = Project(
            name=data.name,
            description=data.description,
            admin_id=user_id,
            scale_min=data.scale_min,
            scale_max=data.scale_max,
            scale_unit=data.scale_unit,
        )
        self._session.add(project)
        self._session.flush()

        membership = ProjectMember(
            project_id=project.id,
            user_id=user_id,
            role=MemberRole.ADMIN,
        )
        self._session.add(membership)
        self._session.commit()
        self._session.refresh(project)
        return project

    def get_user_projects_with_counts(self, user_id: UUID) -> list[tuple[Project, int]]:
        """Get all projects where user is a member, with member counts.

        Uses a single query with subquery to avoid N+1 problem.

        :param user_id: User ID
        :return: List of (project, member_count) tuples
        """
        member_count_subquery = (
            select(ProjectMember.project_id, func.count().label("member_count"))
            .group_by(col(ProjectMember.project_id))
            .subquery()
        )

        statement = (
            select(Project, member_count_subquery.c.member_count)
            .join(ProjectMember, col(ProjectMember.project_id) == Project.id)
            .join(
                member_count_subquery,
                member_count_subquery.c.project_id == Project.id,
            )
            .where(ProjectMember.user_id == user_id)
            .order_by(col(Project.created_at).desc())
        )
        return list(self._session.exec(statement).all())

    def get_project(self, project_id: UUID) -> Project | None:
        """Get project by ID.

        :param project_id: Project UUID
        :return: Project if found, None otherwise
        """
        return self._session.get(Project, project_id)

    def update_project(self, project_id: UUID, data: ProjectUpdate) -> Project:
        """Update project fields.

        :param project_id: Project ID
        :param data: Fields to update (only non-None values applied)
        :return: Updated Project
        :raises ProjectNotFoundError: If project doesn't exist
        """
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        update_data = data.model_dump(exclude_unset=True)

        if "scale_min" in update_data or "scale_max" in update_data:
            new_min = update_data.get("scale_min", project.scale_min)
            new_max = update_data.get("scale_max", project.scale_max)
            if new_min >= new_max:
                msg = f"scale_min ({new_min}) must be less than scale_max ({new_max})"
                raise ScaleRangeError(msg)

        # Explicit field assignment (safer than setattr)
        if "name" in update_data:
            project.name = update_data["name"]
        if "description" in update_data:
            project.description = update_data["description"]
        if "scale_min" in update_data:
            project.scale_min = update_data["scale_min"]
        if "scale_max" in update_data:
            project.scale_max = update_data["scale_max"]
        if "scale_unit" in update_data:
            project.scale_unit = update_data["scale_unit"]

        self._session.add(project)
        self._session.commit()
        self._session.refresh(project)
        return project

    def delete_project(self, project_id: UUID) -> None:
        """Delete project and all related data (cascade).

        :param project_id: Project ID
        :raises ProjectNotFoundError: If project doesn't exist
        """
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        self._session.delete(project)
        self._session.commit()

    def get_members(self, project_id: UUID) -> list[tuple[ProjectMember, User]]:
        """Get all members of a project with user details.

        :param project_id: Project ID
        :return: List of (membership, user) tuples
        """
        statement = (
            select(ProjectMember, User)
            .join(User)
            .where(ProjectMember.project_id == project_id)
            .order_by(col(ProjectMember.joined_at))
        )
        return list(self._session.exec(statement).all())

    def get_member_count(self, project_id: UUID) -> int:
        """Get number of members in a project.

        :param project_id: Project ID
        :return: Member count
        """
        statement = (
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == project_id)
        )
        result = self._session.exec(statement).one()
        return result

    def remove_member(self, project_id: UUID, user_id: UUID) -> None:
        """Remove a member from project.

        :param project_id: Project ID
        :param user_id: User ID to remove
        :raises MemberNotFoundError: If user is not a member of the project
        """
        statement = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        membership = self._session.exec(statement).first()
        if not membership:
            raise MemberNotFoundError(f"User {user_id} is not a member of project {project_id}")

        self._session.delete(membership)
        self._session.commit()

    def is_member(self, project_id: UUID, user_id: UUID) -> bool:
        """Check if user is a member of the project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: True if user is a member
        """
        statement = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        return self._session.exec(statement).first() is not None

    def is_admin(self, project_id: UUID, user_id: UUID) -> bool:
        """Check if user is an admin of the project.

        :param project_id: Project ID
        :param user_id: User ID
        :return: True if user is an admin
        """
        statement = select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role == MemberRole.ADMIN,
        )
        return self._session.exec(statement).first() is not None
