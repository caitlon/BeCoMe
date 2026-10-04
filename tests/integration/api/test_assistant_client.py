"""Integration tests for UserApiClient, exercised through the real app."""

import pytest

from api.assistant.client import UserApiClient
from api.assistant.errors import AssistantNotFoundError, AssistantUpstreamError
from tests.integration.api.conftest import create_project, register_and_login, submit_opinion
from tests.shared.helpers import captured_log_records


class _RecordingASGIApp:
    """Wraps an ASGI app and records each request's method and client address.

    Stands in for a transport-interception library: the client only ever receives
    an app, so wrapping the app itself is the cheapest way to observe what actually
    reaches it, with no new dependency.
    """

    def __init__(self, app):
        self._app = app
        self.methods: list[str] = []
        self.client_hosts: list[str | None] = []

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            self.methods.append(scope["method"])
            client = scope.get("client")
            self.client_hosts.append(client[0] if client else None)
        await self._app(scope, receive, send)


class TestOwnProjectAccess:
    """A signed-in user reads their own project through the assistant's client."""

    @pytest.mark.asyncio
    async def test_sees_own_project_opinions_and_result(self, client):
        """
        GIVEN user A with a project and one submitted opinion
        WHEN UserApiClient reads it back on A's behalf
        THEN the project, its opinions, and its result all come back correctly
        """
        # GIVEN
        token = register_and_login(client, "alice@example.com")
        project = create_project(client, token, name="Alice's project")
        submit_opinion(client, token, project["id"])
        api_client = UserApiClient(app=client.app, access_token=token, client_ip="127.0.0.1")

        # WHEN
        projects = await api_client.list_projects()
        detail = await api_client.get_project(project["id"])
        opinions = await api_client.get_opinions(project["id"])
        result = await api_client.get_result(project["id"])
        await api_client.aclose()

        # THEN
        assert project["id"] in [item.id for item in projects]
        assert detail.id == project["id"]
        assert detail.name == "Alice's project"
        assert len(opinions) == 1
        assert opinions[0].position == "Expert"
        assert result is not None
        assert result.num_experts == 1

    @pytest.mark.asyncio
    async def test_result_is_none_before_any_opinion(self, client):
        """
        GIVEN user A's project with no opinions yet
        WHEN UserApiClient reads its result on A's behalf
        THEN None comes back rather than an error
        """
        # GIVEN
        token = register_and_login(client, "alice@example.com")
        project = create_project(client, token, name="Alice's project")
        api_client = UserApiClient(app=client.app, access_token=token, client_ip="127.0.0.1")

        # WHEN
        result = await api_client.get_result(project["id"])
        await api_client.aclose()

        # THEN
        assert result is None


class TestCrossTenantIsolation:
    """A second user gets the same refusal the UI would, never someone else's data."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name", ["get_project", "get_result", "get_opinions"])
    async def test_other_user_gets_not_found_on_someone_elses_project(self, client, method_name):
        """
        GIVEN user A's project with one submitted opinion
        WHEN user B's UserApiClient reads it through a per-project method
        THEN AssistantNotFoundError is raised, the same 404 the UI would get
        """
        # GIVEN
        owner_token = register_and_login(client, "alice@example.com")
        project = create_project(client, owner_token, name="Alice's project")
        submit_opinion(client, owner_token, project["id"])
        other_token = register_and_login(client, "bob@example.com")
        api_client = UserApiClient(app=client.app, access_token=other_token, client_ip="127.0.0.1")

        # WHEN/THEN
        with pytest.raises(AssistantNotFoundError):
            await getattr(api_client, method_name)(project["id"])
        await api_client.aclose()

    @pytest.mark.asyncio
    async def test_other_users_project_list_leaves_out_someone_elses_project(self, client):
        """
        GIVEN user A's project and user B's own project
        WHEN user B's UserApiClient lists projects
        THEN B's project is there and A's is not
        """
        # GIVEN
        owner_token = register_and_login(client, "alice@example.com")
        project = create_project(client, owner_token, name="Alice's project")
        other_token = register_and_login(client, "bob@example.com")
        own_project = create_project(client, other_token, name="Bob's project")
        api_client = UserApiClient(app=client.app, access_token=other_token, client_ip="127.0.0.1")

        # WHEN
        projects = await api_client.list_projects()
        await api_client.aclose()

        # THEN
        listed = [item.id for item in projects]
        assert own_project["id"] in listed
        assert project["id"] not in listed


class TestUpstreamErrors:
    """Any refusal other than 404 surfaces as AssistantUpstreamError, never as data."""

    @pytest.mark.asyncio
    async def test_a_token_the_api_rejects_raises_upstream_error(self, client):
        """
        GIVEN a client carrying a token the API does not accept
        WHEN it lists projects
        THEN AssistantUpstreamError is raised, since the API answers 401
        """
        # GIVEN
        api_client = UserApiClient(
            app=client.app, access_token="not-a-valid-token", client_ip="127.0.0.1"
        )

        # WHEN/THEN
        with pytest.raises(AssistantUpstreamError):
            await api_client.list_projects()
        await api_client.aclose()


class TestAllowlist:
    """The client never hands back a field the model must not see."""

    @pytest.mark.asyncio
    async def test_output_never_carries_email_user_id_or_photo_url(self, client):
        """
        GIVEN a project with one submitted opinion
        WHEN its details and opinions are read through UserApiClient
        THEN neither dump carries user_email, user_id, or photo_url
        """
        # GIVEN
        token = register_and_login(client, "alice@example.com")
        project = create_project(client, token, name="Alice's project")
        submit_opinion(client, token, project["id"])
        api_client = UserApiClient(app=client.app, access_token=token, client_ip="127.0.0.1")

        # WHEN
        detail = await api_client.get_project(project["id"])
        opinions = await api_client.get_opinions(project["id"])
        await api_client.aclose()

        # THEN
        for view in (detail, *opinions):
            dumped = view.model_dump()
            assert "user_email" not in dumped
            assert "user_id" not in dumped
            assert "photo_url" not in dumped


class TestTransportDiscipline:
    """The client can only ever read, and it reads as the real caller."""

    @pytest.mark.asyncio
    async def test_transport_never_sees_a_non_get_method(self, client):
        """
        GIVEN a recording ASGI wrapper around the real app
        WHEN every UserApiClient method is called
        THEN the wrapper only ever observes the GET method
        """
        # GIVEN
        token = register_and_login(client, "alice@example.com")
        project = create_project(client, token, name="Alice's project")
        submit_opinion(client, token, project["id"])
        recorder = _RecordingASGIApp(client.app)
        api_client = UserApiClient(app=recorder, access_token=token, client_ip="203.0.113.7")

        # WHEN
        await api_client.list_projects()
        await api_client.get_project(project["id"])
        await api_client.get_opinions(project["id"])
        await api_client.get_result(project["id"])
        await api_client.aclose()

        # THEN
        assert recorder.methods
        assert set(recorder.methods) == {"GET"}

    @pytest.mark.asyncio
    async def test_the_callers_own_ip_reaches_the_asgi_scope(self, client):
        """
        GIVEN a UserApiClient constructed with the caller's own IP
        WHEN a request is made
        THEN that IP is what the ASGI scope carries as scope["client"]

        get_client_ip (api/utils/client_ip.py) reads request.client.host on a
        local, non-deployed profile, and Starlette builds request.client from
        scope["client"] -- so this is what a rate-limit or security-log entry for
        this internal call would key on, not "testclient" or "unknown".
        """
        # GIVEN
        token = register_and_login(client, "alice@example.com")
        recorder = _RecordingASGIApp(client.app)
        api_client = UserApiClient(app=recorder, access_token=token, client_ip="203.0.113.7")

        # WHEN
        await api_client.list_projects()
        await api_client.aclose()

        # THEN
        assert recorder.client_hosts == ["203.0.113.7"]


class TestTokenNeverLogged:
    """The bearer token this client carries must never reach a log record."""

    @pytest.mark.asyncio
    async def test_access_token_does_not_appear_in_any_log_record(self, client):
        """
        GIVEN a real access token used to list and read projects through UserApiClient
        WHEN every api.* log record emitted during those calls is captured
        THEN records were emitted, and the raw token appears in none of them,
            neither message nor extra

        Listing projects is what makes this test able to fail: the project query
        service logs on every list, while reading one project logs nothing on the
        test app, so without the list call the loop below would check nothing.
        """
        # GIVEN
        token = register_and_login(client, "alice@example.com")
        project = create_project(client, token, name="Alice's project")
        api_client = UserApiClient(app=client.app, access_token=token, client_ip="127.0.0.1")

        # WHEN
        with captured_log_records("api") as records:
            await api_client.list_projects()
            await api_client.get_project(project["id"])
        await api_client.aclose()

        # THEN
        assert records
        for record in records:
            assert token not in record.getMessage()
            assert all(token not in str(value) for value in record.__dict__.values())
