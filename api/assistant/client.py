"""HTTP client the assistant uses to read data as the signed-in user.

Every call goes through the real API over an in-process ASGI transport, carrying
the caller's own access token and IP, so project access is governed by the same
RequireProjectAccess dependency the browser UI goes through. The client issues GET
requests only: it has no method that could write anything. Where a Cloudflare origin
secret is configured, each request also carries the origin-verify header and the caller's
IP, so the inner rate-limit key resolves to the caller's own; those headers never leave
the process, and the secret is never logged.
"""

from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Any
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError
from starlette.types import ASGIApp

from api.assistant.errors import AssistantNotFoundError, AssistantUpstreamError
from api.assistant.views import OpinionView, ProjectBrief, ProjectView, ResultView
from api.config import get_settings
from api.pagination import MAX_PAGE_SIZE

# A loopback host: the request never leaves this process, so plain http exposes nothing.
_INTERNAL_BASE_URL = "http://localhost"

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


def _validate[ModelT: BaseModel](model: type[ModelT], data: Any) -> ModelT:
    """Validate one response body against a view schema.

    A 2xx answer that does not fit the schema is a fault on the API's side, so it
    surfaces as the same error as any other unusable answer. The message names the
    schema and the failing field locations, never a value: the body is project data,
    and pydantic's own error text repeats it. The new error is raised outside the
    ``except`` block, so the validation error is neither its cause nor its context and
    cannot reach a log record through the exception chain.

    :param model: The view schema to validate against.
    :param data: The decoded JSON body, or one item of it.
    :return: The validated view.
    :raises AssistantUpstreamError: If data does not fit the schema.
    """
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        locations = ", ".join(
            ".".join(str(part) for part in error["loc"]) or "<root>" for error in exc.errors()
        )
    raise AssistantUpstreamError(
        f"a response body failed the {model.__name__} schema at: {locations}"
    )


class UserApiClient:
    """Read-only view of the API, scoped to one signed-in user's own access.

    :param app: The ASGI application to call in-process (no network hop).
    :param access_token: The caller's own JWT access token.
    :param client_ip: The caller's own client IP, so rate limiting and security
        logging key on the real user rather than on this internal call.
    """

    def __init__(self, app: ASGIApp, access_token: str, client_ip: str) -> None:
        transport = httpx.ASGITransport(app=app, client=(client_ip, 0))
        headers = {"Authorization": f"Bearer {access_token}"}
        # get_client_ip trusts CF-Connecting-IP only behind a matching X-Origin-Verify
        # and otherwise keys every request under one constant, which would put all
        # users' internal reads into one bucket. Without a secret (local, CI) the ASGI
        # peer above already carries the IP.
        origin_secret = get_settings().cloudflare_origin_secret
        if origin_secret:
            headers["X-Origin-Verify"] = origin_secret
            headers["CF-Connecting-IP"] = client_ip
        self._http = httpx.AsyncClient(
            transport=transport,
            base_url=_INTERNAL_BASE_URL,
            headers=headers,
            # A jar that stores nothing. The API reads a session cookie before the
            # Authorization header, so a cookie kept from one response would outrank
            # the token this client was built with.
            cookies=CookieJar(policy=DefaultCookiePolicy(allowed_domains=[])),
        )

    async def _get_json(self, path: str, params: dict[str, int | bool] | None = None) -> Any:
        """Issue the one kind of request this client ever sends and decode its body.

        :param path: API path to read, e.g. "/api/v1/projects".
        :param params: Query parameters, used for pagination and the opinions view.
        :return: The decoded JSON body.
        :raises AssistantNotFoundError: On a 404 response.
        :raises AssistantUpstreamError: On any other non-2xx response, or a 2xx whose
            body is not JSON. The message never carries any of the body.
        """
        response = await self._http.get(path, params=params)
        if response.status_code == httpx.codes.NOT_FOUND:
            raise AssistantNotFoundError(f"{path} returned 404")
        if response.is_error:
            raise AssistantUpstreamError(f"{path} returned {response.status_code}")
        try:
            return response.json()
        except ValueError:
            pass
        raise AssistantUpstreamError(f"{path} returned a body that is not JSON")

    async def _get_all(self, path: str, extra_params: dict[str, bool] | None = None) -> list[Any]:
        """Read every page of a paginated list endpoint.

        The list endpoints return at most MAX_PAGE_SIZE items per request, so one
        request alone would silently drop the rest. A page shorter than that is the
        last one.

        :param path: API path of a list endpoint that takes limit and offset.
        :param extra_params: Query parameters sent with every page, next to the paging ones.
        :return: The items of every page, in the order the API returns them.
        :raises AssistantUpstreamError: If a page is not a list, or the list runs past
            _MAX_PAGES full pages.
        """
        items: list[Any] = []
        for _ in range(_MAX_PAGES):
            params = {**(extra_params or {}), "limit": MAX_PAGE_SIZE, "offset": len(items)}
            page = await self._get_json(path, params=params)
            if not isinstance(page, list):
                raise AssistantUpstreamError(f"{path} returned a page that is not a list")
            items.extend(page)
            if len(page) < MAX_PAGE_SIZE:
                return items
        raise AssistantUpstreamError(f"{path} ran past {_MAX_PAGES} full pages")

    async def list_projects(self) -> list[ProjectBrief]:
        """List the projects the caller is a member of.

        :return: One ProjectBrief per project, across every page.
        :raises AssistantUpstreamError: If the API refuses the request, answers with a
            body that fails the schema, or the list runs past _MAX_PAGES full pages.
        """
        items = await self._get_all("/api/v1/projects")
        return [_validate(ProjectBrief, item) for item in items]

    async def get_project(self, project_id: str) -> ProjectView:
        """Get one project's details.

        :param project_id: Project UUID, as a string.
        :return: The project's allowlisted details.
        :raises AssistantNotFoundError: If project_id is not a valid UUID, or the
            caller cannot see this project.
        :raises AssistantUpstreamError: If the API answers with any other error, or with
            a body that is not JSON or fails the schema.
        """
        body = await self._get_json(f"/api/v1/projects/{_canonical_project_id(project_id)}")
        return _validate(ProjectView, body)

    async def get_result(self, project_id: str) -> ResultView | None:
        """Get a project's calculation result.

        :param project_id: Project UUID, as a string.
        :return: The result, or None if no opinions have been submitted yet.
        :raises AssistantNotFoundError: If project_id is not a valid UUID, or the
            caller cannot see this project.
        :raises AssistantUpstreamError: If the API answers with any other error, or with
            a body that is not JSON or fails the schema.
        """
        body = await self._get_json(f"/api/v1/projects/{_canonical_project_id(project_id)}/result")
        return _validate(ResultView, body) if body is not None else None

    async def get_opinions(self, project_id: str, *, full: bool = False) -> list[OpinionView]:
        """List a project's expert opinions, as the assistant may show them to the caller.

        Opinions of members who objected to the assistant are left out, except the
        caller's own. ``full=True`` lifts that and exists only for the trace mask, which
        has to know every name; what it returns must never reach the model.

        :param project_id: Project UUID, as a string.
        :param full: Read the complete list, objectors included.
        :return: One OpinionView per submitted opinion, across every page.
        :raises AssistantNotFoundError: If project_id is not a valid UUID, or the
            caller cannot see this project.
        :raises AssistantUpstreamError: If the API answers with any other error, a body
            that is not JSON or fails the schema, or the list runs past _MAX_PAGES full pages.
        """
        path = f"/api/v1/projects/{_canonical_project_id(project_id)}/opinions"
        extra = {} if full else {"for_assistant": True}
        return [_validate(OpinionView, item) for item in await self._get_all(path, extra)]

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()
