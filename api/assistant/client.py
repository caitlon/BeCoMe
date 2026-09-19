"""HTTP client the assistant uses to read data as the signed-in user.

Every call goes through the real API over an in-process ASGI transport, carrying
the caller's own access token and IP, so project access is governed by the same
RequireProjectAccess dependency the browser UI goes through. The client issues GET
requests only: it has no method that could write anything.
"""

from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Any
from uuid import UUID

import httpx
from starlette.types import ASGIApp

from api.assistant.errors import AssistantNotFoundError, AssistantUpstreamError
from api.assistant.views import OpinionView, ProjectBrief, ProjectView, ResultView
from api.pagination import MAX_PAGE_SIZE

_INTERNAL_BASE_URL = "http://assistant.internal"

# The most pages one list read follows. 1,000 rows is far past any real expert panel
# or project list, so this only stops a runaway read; it never trims a real one.
_MAX_PAGES = 10


def _canonical_project_id(project_id: str) -> str:
    """Return a project id in canonical form, refusing anything that is not a UUID.

    Only this form is ever put into a request path, so a model-supplied string can
    never add a path segment or a query of its own.

    :param project_id: Candidate project UUID, as a string.
    :return: The UUID in canonical lower-case hyphenated form.
    :raises AssistantNotFoundError: If project_id does not parse as a UUID.
    """
    try:
        return str(UUID(project_id))
    except ValueError as exc:
        raise AssistantNotFoundError(f"{project_id!r} is not a valid project id") from exc


class UserApiClient:
    """Read-only view of the API, scoped to one signed-in user's own access.

    :param app: The ASGI application to call in-process (no network hop).
    :param access_token: The caller's own JWT access token.
    :param client_ip: The caller's own client IP, so rate limiting and security
        logging key on the real user rather than on this internal call.
    """

    def __init__(self, app: ASGIApp, access_token: str, client_ip: str) -> None:
        transport = httpx.ASGITransport(app=app, client=(client_ip, 0))
        self._http = httpx.AsyncClient(
            transport=transport,
            base_url=_INTERNAL_BASE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            # A jar that stores nothing. The API reads a session cookie before the
            # Authorization header, so a cookie kept from one response would outrank
            # the token this client was built with.
            cookies=CookieJar(policy=DefaultCookiePolicy(allowed_domains=[])),
        )

    async def _get(self, path: str, params: dict[str, int] | None = None) -> httpx.Response:
        """Issue the one kind of request this client ever sends.

        :param path: API path to read, e.g. "/api/v1/projects".
        :param params: Query parameters, used only for pagination.
        :return: The successful response.
        :raises AssistantNotFoundError: On a 404 response.
        :raises AssistantUpstreamError: On any other non-2xx response.
        """
        response = await self._http.get(path, params=params)
        if response.status_code == httpx.codes.NOT_FOUND:
            raise AssistantNotFoundError(f"{path} returned 404")
        if response.is_error:
            raise AssistantUpstreamError(f"{path} returned {response.status_code}")
        return response

    async def _get_all(self, path: str) -> list[Any]:
        """Read every page of a paginated list endpoint.

        The list endpoints return at most MAX_PAGE_SIZE items per request, so one
        request alone would silently drop the rest. A page shorter than that is the
        last one.

        :param path: API path of a list endpoint that takes limit and offset.
        :return: The items of every page, in the order the API returns them.
        :raises AssistantUpstreamError: If the list runs past _MAX_PAGES full pages.
        """
        items: list[Any] = []
        for _ in range(_MAX_PAGES):
            params = {"limit": MAX_PAGE_SIZE, "offset": len(items)}
            page = (await self._get(path, params=params)).json()
            items.extend(page)
            if len(page) < MAX_PAGE_SIZE:
                return items
        raise AssistantUpstreamError(f"{path} ran past {_MAX_PAGES} full pages")

    async def list_projects(self) -> list[ProjectBrief]:
        """List the projects the caller is a member of.

        :return: One ProjectBrief per project, across every page.
        :raises AssistantUpstreamError: If the API refuses the request, or the list
            runs past _MAX_PAGES full pages.
        """
        items = await self._get_all("/api/v1/projects")
        return [ProjectBrief.model_validate(item) for item in items]

    async def get_project(self, project_id: str) -> ProjectView:
        """Get one project's details.

        :param project_id: Project UUID, as a string.
        :return: The project's allowlisted details.
        :raises AssistantNotFoundError: If project_id is not a valid UUID, or the
            caller cannot see this project.
        :raises AssistantUpstreamError: If the API answers with any other error.
        """
        response = await self._get(f"/api/v1/projects/{_canonical_project_id(project_id)}")
        return ProjectView.model_validate(response.json())

    async def get_result(self, project_id: str) -> ResultView | None:
        """Get a project's calculation result.

        :param project_id: Project UUID, as a string.
        :return: The result, or None if no opinions have been submitted yet.
        :raises AssistantNotFoundError: If project_id is not a valid UUID, or the
            caller cannot see this project.
        :raises AssistantUpstreamError: If the API answers with any other error.
        """
        response = await self._get(f"/api/v1/projects/{_canonical_project_id(project_id)}/result")
        body = response.json()
        return ResultView.model_validate(body) if body is not None else None

    async def get_opinions(self, project_id: str) -> list[OpinionView]:
        """List a project's expert opinions.

        :param project_id: Project UUID, as a string.
        :return: One OpinionView per submitted opinion, across every page.
        :raises AssistantNotFoundError: If project_id is not a valid UUID, or the
            caller cannot see this project.
        :raises AssistantUpstreamError: If the API answers with any other error, or
            the list runs past _MAX_PAGES full pages.
        """
        path = f"/api/v1/projects/{_canonical_project_id(project_id)}/opinions"
        return [OpinionView.model_validate(item) for item in await self._get_all(path)]

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()
