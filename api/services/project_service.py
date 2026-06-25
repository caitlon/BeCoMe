"""Project business logic service."""

import logging
from uuid import UUID

from sqlmodel import func, select

from api.db.models import MemberRole, Project, ProjectMember
from api.exceptions import MemberNotFoundError, ProjectNotFoundError, ScaleRangeError
from api.schemas.project import ProjectCreate, ProjectUpdate
from api.services.base import BaseService

logger = logging.getLogger("api.service.project")


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
        logger.info(
            "Project created",
            extra={
                "event": "project_created",
                "project_id": str(project.id),
                "user_id": str(user_id),
            },
        )
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

        saved = self._save_and_refresh(project)
        logger.info(
            "Project updated",
            extra={"event": "project_updated", "project_id": str(project_id)},
        )
        return saved

    def delete_project(self, project_id: UUID) -> None:
        """Delete project and all related data (cascade).

        :param project_id: Project ID
        :raises ProjectNotFoundError: If project doesn't exist
        """
        project = self.get_project(project_id)
        if not project:
            raise ProjectNotFoundError(f"Project {project_id} not found")

        self._delete_and_commit(project)
        logger.info(
            "Project deleted",
            extra={"event": "project_deleted", "project_id": str(project_id)},
        )

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

    def get_owned_projects(self, user_id: UUID) -> list[Project]:
        """Get all projects the user owns (is admin of).

        :param user_id: User ID
        :return: Projects whose admin is the user
        """
        statement = select(Project).where(Project.admin_id == user_id)
        return list(self._session.exec(statement).all())

    def transfer_ownership(self, project: Project, new_admin_id: UUID) -> Project:
        """Transfer project ownership to another member.

        Keeps both ownership sources in sync atomically: ``Project.admin_id`` and
        the ``ProjectMember`` role rows -- the new owner becomes admin and the
        former owner is demoted to expert.

        :param project: Project to transfer (current admin already verified)
        :param new_admin_id: User ID of the member to promote to admin
        :return: Updated project
        :raises MemberNotFoundError: If the target user is not a project member
        """
        new_admin_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == new_admin_id,
            )
        ).first()
        if not new_admin_membership:
            raise MemberNotFoundError(
                f"User {new_admin_id} is not a member of project {project.id}"
            )

        old_admin_membership = self._session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == project.admin_id,
            )
        ).first()

        project.admin_id = new_admin_id
        new_admin_membership.role = MemberRole.ADMIN
        self._session.add(project)
        self._session.add(new_admin_membership)
        if old_admin_membership:
            old_admin_membership.role = MemberRole.EXPERT
            self._session.add(old_admin_membership)
        self._session.commit()
        self._session.refresh(project)
        logger.info(
            "Project ownership transferred",
            extra={
                "event": "ownership_transferred",
                "project_id": str(project.id),
                "new_admin_id": str(new_admin_id),
            },
        )
        return project
