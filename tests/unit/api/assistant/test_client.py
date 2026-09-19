"""Unit tests for UserApiClient's request discipline (fakes only, no network)."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request, Response

from api.assistant.client import _MAX_PAGES, UserApiClient
from api.assistant.errors import AssistantNotFoundError, AssistantUpstreamError
from api.pagination import MAX_PAGE_SIZE


class _ExplodingApp:
    """An ASGI app that fails loudly if it is ever actually called."""

    async def __call__(self, scope, receive, send):
        raise AssertionError("the client sent a request for an invalid project id")


def _opinion_row(n: int) -> dict[str, Any]:
    """Build one OpinionResponse-shaped row for a stand-in list endpoint.

    :param n: Row number, used to tell the experts apart.
    :return: The row as the real endpoint would serialise it.
    """
    return {
        "user_first_name": f"Expert {n}",
        "user_last_name": None,
        "position": "Expert",
        "lower_bound": 10.0,
        "peak": 20.0,
        "upper_bound": 30.0,
        "centroid": 20.0,
    }


class TestInvalidProjectId:
    """A malformed project id is refused before any request is sent."""

    @pytest.mark.asyncio
    async def test_get_project_rejects_a_non_uuid_without_a_request(self):
        """
        GIVEN a client whose transport would fail loudly if ever called
        WHEN get_project is called with a string that is not a UUID
        THEN AssistantNotFoundError is raised and the transport is never touched
        """
        # GIVEN
        api_client = UserApiClient(app=_ExplodingApp(), access_token="t", client_ip="127.0.0.1")

        # WHEN/THEN
        with pytest.raises(AssistantNotFoundError):
            await api_client.get_project("not-a-uuid")
        await api_client.aclose()

    @pytest.mark.asyncio
    async def test_get_result_rejects_a_non_uuid_without_a_request(self):
        """
        GIVEN a client whose transport would fail loudly if ever called
        WHEN get_result is called with a string that is not a UUID
        THEN AssistantNotFoundError is raised and the transport is never touched
        """
        # GIVEN
        api_client = UserApiClient(app=_ExplodingApp(), access_token="t", client_ip="127.0.0.1")

        # WHEN/THEN
        with pytest.raises(AssistantNotFoundError):
            await api_client.get_result("not-a-uuid")
        await api_client.aclose()

    @pytest.mark.asyncio
    async def test_get_opinions_rejects_a_non_uuid_without_a_request(self):
        """
        GIVEN a client whose transport would fail loudly if ever called
        WHEN get_opinions is called with a string that is not a UUID
        THEN AssistantNotFoundError is raised and the transport is never touched
        """
        # GIVEN
        api_client = UserApiClient(app=_ExplodingApp(), access_token="t", client_ip="127.0.0.1")

        # WHEN/THEN
        with pytest.raises(AssistantNotFoundError):
            await api_client.get_opinions("not-a-uuid")
        await api_client.aclose()


class TestCanonicalProjectId:
    """Only the canonical form of a project id is ever put into a request path."""

    @pytest.mark.asyncio
    async def test_a_braced_upper_case_uuid_is_sent_in_canonical_form(self):
        """
        GIVEN a valid project id written in upper case inside braces
        WHEN get_project is called with it
        THEN the request path carries the canonical lower-case hyphenated form
        """
        # GIVEN
        project_id = uuid4()
        seen: list[str] = []
        app = FastAPI()

        @app.get("/api/v1/projects/{raw_id}")
        def read_project(raw_id: str) -> dict[str, Any]:
            seen.append(raw_id)
            return {
                "id": raw_id,
                "name": "Flood risk",
                "description": None,
                "scale_min": 0.0,
                "scale_max": 100.0,
                "scale_unit": "%",
                "role": "admin",
            }

        api_client = UserApiClient(app=app, access_token="t", client_ip="127.0.0.1")

        # WHEN
        await api_client.get_project("{" + str(project_id).upper() + "}")
        await api_client.aclose()

        # THEN
        assert seen == [str(project_id)]


class TestPagination:
    """List methods read every page, not only the first one the API returns."""

    @pytest.mark.asyncio
    async def test_get_opinions_reads_past_the_first_page(self):
        """
        GIVEN a project with one more opinion than fits on one page
        WHEN get_opinions is called
        THEN every opinion comes back, read over two requests
        """
        # GIVEN
        rows = [_opinion_row(n) for n in range(MAX_PAGE_SIZE + 1)]
        asked: list[tuple[int, int]] = []
        app = FastAPI()

        @app.get("/api/v1/projects/{project_id}/opinions")
        def list_opinions(project_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
            asked.append((limit, offset))
            return rows[offset : offset + limit]

        api_client = UserApiClient(app=app, access_token="t", client_ip="127.0.0.1")

        # WHEN
        opinions = await api_client.get_opinions(str(uuid4()))
        await api_client.aclose()

        # THEN
        assert len(opinions) == MAX_PAGE_SIZE + 1
        assert opinions[-1].expert_name == f"Expert {MAX_PAGE_SIZE}"
        assert asked == [(MAX_PAGE_SIZE, 0), (MAX_PAGE_SIZE, MAX_PAGE_SIZE)]

    @pytest.mark.asyncio
    async def test_list_projects_stops_at_an_empty_page(self):
        """
        GIVEN exactly one full page of projects
        WHEN list_projects is called
        THEN it asks once more, gets an empty page, and returns the full page
        """
        # GIVEN
        rows = [
            {"id": str(uuid4()), "name": f"Project {n}", "role": "expert", "is_example": False}
            for n in range(MAX_PAGE_SIZE)
        ]
        asked: list[tuple[int, int]] = []
        app = FastAPI()

        @app.get("/api/v1/projects")
        def list_projects(limit: int, offset: int) -> list[dict[str, Any]]:
            asked.append((limit, offset))
            return rows[offset : offset + limit]

        api_client = UserApiClient(app=app, access_token="t", client_ip="127.0.0.1")

        # WHEN
        projects = await api_client.list_projects()
        await api_client.aclose()

        # THEN
        assert [project.id for project in projects] == [row["id"] for row in rows]
        assert asked == [(MAX_PAGE_SIZE, 0), (MAX_PAGE_SIZE, MAX_PAGE_SIZE)]

    @pytest.mark.asyncio
    async def test_a_list_that_never_ends_stops_with_an_upstream_error(self):
        """
        GIVEN a list endpoint that answers every request with a full page
        WHEN list_projects is called
        THEN it gives up after _MAX_PAGES requests with AssistantUpstreamError
        """
        # GIVEN
        full_page = [
            {"id": str(uuid4()), "name": f"Project {n}", "role": "expert", "is_example": False}
            for n in range(MAX_PAGE_SIZE)
        ]
        asked: list[int] = []
        app = FastAPI()

        @app.get("/api/v1/projects")
        def list_projects(offset: int) -> list[dict[str, Any]]:
            asked.append(offset)
            return full_page

        api_client = UserApiClient(app=app, access_token="t", client_ip="127.0.0.1")

        # WHEN/THEN
        with pytest.raises(AssistantUpstreamError):
            await api_client.list_projects()
        await api_client.aclose()
        assert len(asked) == _MAX_PAGES


class TestNoCookies:
    """The client authenticates only with the token it was built with."""

    @pytest.mark.asyncio
    async def test_a_cookie_set_by_a_response_is_never_sent_back(self):
        """
        GIVEN an API that sets a cookie on its response
        WHEN the client makes a second request
        THEN that request carries no cookie, so only the bearer token identifies the caller
        """
        # GIVEN
        cookie_headers: list[str | None] = []
        app = FastAPI()

        @app.get("/api/v1/projects")
        def list_projects(request: Request, response: Response) -> list[dict[str, Any]]:
            cookie_headers.append(request.headers.get("cookie"))
            response.set_cookie("access", "another-identity")
            return []

        api_client = UserApiClient(app=app, access_token="t", client_ip="127.0.0.1")

        # WHEN
        await api_client.list_projects()
        await api_client.list_projects()
        await api_client.aclose()

        # THEN
        assert cookie_headers == [None, None]
