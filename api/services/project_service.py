"""Project business logic service."""

from uuid import UUID

from sqlmodel import func, select

from api.db.models import MemberRole, Project, ProjectMember
from api.exceptions import ProjectNotFoundError, ScaleRangeError
from api.schemas.project import ProjectCreate, ProjectUpdate
from api.services.base import BaseService


class ProjectService(BaseService):
    """Service for project CRUD operations.

    For membership operations, use ProjectMembershipService.
    For complex queries, use ProjectQueryService.
    """

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
        :raises ScaleRangeError: If scale range becomes invalid
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

        return self._save_and_refresh(project)

    def delete_project(self, project_id: UUID) -> None:
        """Delete project and all related data (cascade).

        :param project_id: Project ID
        :raises ProjectNotFoundError: If project doesn't exist
        """
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        self._delete_and_commit(project)

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
        return self._session.exec(statement).one()
