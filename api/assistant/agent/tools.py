"""LangChain tools exposed to the assistant agent, scoped to the caller's own data.

Every reply a tool gives the model is a data block, or one line that starts with one of
three fixed prefixes.

- ``not_found:`` the caller cannot see the project, or the id is not a project id (the
  API client refuses such an id before it sends anything). The text does not say whether
  the project exists.
- ``unavailable:`` a service the tool depends on failed. A failing API is never reported
  as not found.
- ``no_result:`` the request was fine and there is nothing to show. Each case has its
  own text (no result yet, no opinions, no passages, no projects).

No reply carries the text of an exception. Text written by users (project names,
descriptions, expert names and positions) goes through
:func:`~api.assistant.agent.prompt.clean_text` before it enters a reply, so it cannot
close a ``<project_data>`` block or start a line of its own.

The functions that write a data block (``render_project``, ``render_project_list``,
``render_opinions``) are public: the chat service calls the same ones for what it
fetches ahead of the model, so a fact is written one way wherever the model meets it.
"""

import logging
from collections.abc import Sequence

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from api.assistant.agent.context import AssistantContext
from api.assistant.agent.prompt import (
    LABEL_LIMIT,
    clean_text,
    format_excerpt,
    format_number,
    render_context_block,
)
from api.assistant.errors import AssistantNotFoundError, AssistantUpstreamError
from api.assistant.upstream import UNAVAILABLE_ERRORS
from api.assistant.views import OpinionView, ProjectBrief, ProjectView

logger = logging.getLogger(__name__)

_NOT_FOUND = "not_found: no such project, or you are not a member of it"
# Public because the chat service gives the model this same line when a tool fails in a
# way the tool did not handle.
UNAVAILABLE_REPLY = (
    "unavailable: the data could not be read right now; ask the user to try again later"
)
# The four empty cases share one prefix and each says what is missing, so the model can
# tell the user which thing it is.
_NO_RESULT_YET = "no_result: no result has been calculated for this project yet"
_NO_OPINIONS = "no_result: no opinions have been submitted to this project yet"
_NO_PASSAGES = "no_result: no matching passages in the documentation"
_NO_PROJECTS = "no_result: the user is not a member of any project"

# What the model reads about each tool. The docstring below each tool is for developers;
# this text is all the model sees, so it says what the one argument is.
_SEARCH_DOCS_DESCRIPTION = (
    "Search the BeCoMe documentation for passages about the method, the application or "
    "how to read a result. Argument query: what to look for, in the user's own words. "
    "Cite every passage you use with its number, like [1]."
)
_LIST_MY_PROJECTS_DESCRIPTION = (
    "List the projects the user is a member of, with each project's id and the user's "
    "role in it. Takes no arguments."
)
_GET_PROJECT_DESCRIPTION = (
    "Get the name, description and scale of one of the user's projects. Argument "
    "project_id: the project's id, from the project list or the current project."
)
_GET_PROJECT_RESULT_DESCRIPTION = (
    "Get the calculated result of one of the user's projects: the best compromise, the "
    "mean, the median, the maximum error and the agreement level. Argument project_id: "
    "the project's id, from the project list or the current project."
)
_GET_PROJECT_OPINIONS_DESCRIPTION = (
    "Get the individual expert opinions of one of the user's projects, at most 50. "
    "Argument project_id: the project's id, from the project list or the current project."
)

# Limits on the free text a reply carries, in characters. Fifty opinion rows must stay
# small in a 16k-token window, so an expert's name and position are the tightest.
_NAME_LIMIT = 120
_EXPERT_LIMIT = 60
_DESCRIPTION_LIMIT = 1000
_UNIT_LIMIT = 20
_ID_LIMIT = 40

# What the API client can fail with, as far as a tool is concerned: its own refusal of an
# answer, and whatever the in-process transport re-raises from a route that did not handle
# it (a database failure, say), which reaches the tool unchanged.
_BACKEND_FAILURES: tuple[type[Exception], ...] = (AssistantUpstreamError, *UNAVAILABLE_ERRORS)

_MAX_PROJECTS = 50
_MAX_OPINIONS = 50


def _block(lines: Sequence[str]) -> str:
    """Wrap lines in a ``<project_data>`` block.

    :param lines: The block's lines, already cleaned.
    :return: The finished block.
    """
    return "\n".join(["<project_data>", *lines, "</project_data>"])


def render_project(project: ProjectView) -> str:
    """Render one project's details as a data block.

    :param project: The project's allowlisted details.
    :return: The block: name, description, scale and the caller's role.
    """
    scale = f"{format_number(project.scale_min)} to {format_number(project.scale_max)}"
    unit = clean_text(project.scale_unit, _UNIT_LIMIT)
    if unit:
        scale += f" {unit}"
    description = clean_text(project.description or "", _DESCRIPTION_LIMIT) or "(none)"
    return _block(
        [
            f"Name: {clean_text(project.name, _NAME_LIMIT)}",
            f"Description: {description}",
            f"Scale: {scale}",
            f"Your role: {clean_text(project.role, LABEL_LIMIT)}",
        ]
    )


def render_project_list(projects: Sequence[ProjectBrief]) -> str:
    """Render the caller's projects as a data block.

    The block has a count line, then at most 50 projects, then ``... and N more
    projects`` when there are more.

    :param projects: The caller's projects.
    :return: The block: each project's id, name and role.
    """
    lines = [f"Number of projects: {len(projects)}"]
    for project in projects[:_MAX_PROJECTS]:
        lines.append(
            f"- {clean_text(project.id, _ID_LIMIT)}: {clean_text(project.name, _NAME_LIMIT)} "
            f"({clean_text(project.role, LABEL_LIMIT)})"
        )
    if len(projects) > _MAX_PROJECTS:
        lines.append(f"... and {len(projects) - _MAX_PROJECTS} more projects")
    return _block(lines)


def render_opinions(opinions: Sequence[OpinionView]) -> str:
    """Render a project's expert opinions as a data block.

    The block has a count line, then at most 50 opinions, then ``... and N more
    opinions`` when there are more.

    :param opinions: The project's opinions.
    :return: The block.
    """
    lines = [f"Number of opinions: {len(opinions)}"]
    for opinion in opinions[:_MAX_OPINIONS]:
        name = clean_text(opinion.expert_name, _EXPERT_LIMIT)
        position = clean_text(opinion.position, _EXPERT_LIMIT)
        lines.append(
            f"- {name} ({position}): lower={format_number(opinion.lower_bound)}, "
            f"peak={format_number(opinion.peak)}, upper={format_number(opinion.upper_bound)}, "
            f"centroid={format_number(opinion.centroid)}"
        )
    if len(opinions) > _MAX_OPINIONS:
        lines.append(f"... and {len(opinions) - _MAX_OPINIONS} more opinions")
    return _block(lines)


def _reply(ctx: AssistantContext, text: str) -> str:
    """Keep a reply as grounding for the number check and hand it back.

    :param ctx: The turn's context.
    :param text: The reply.
    :return: The same text.
    """
    ctx.tool_outputs.append(text)
    return text


def _unavailable(tool_name: str, exc: Exception) -> str:
    """Log that a tool could not reach its backend and give the fixed reply.

    The record carries the tool and the exception's class name only: never the
    message, which can name a host or a path, and never a traceback.

    :param tool_name: The tool that failed.
    :param exc: The failure.
    :return: The ``unavailable:`` line.
    """
    logger.warning(
        "assistant tool %s could not reach its backend",
        tool_name,
        extra={
            "event": "assistant_tool_unavailable",
            "tool": tool_name,
            "reason": type(exc).__name__,
        },
    )
    return UNAVAILABLE_REPLY


@tool(description=_SEARCH_DOCS_DESCRIPTION)
async def search_docs(query: str, runtime: ToolRuntime[AssistantContext]) -> str:
    """Search the BeCoMe documentation and return the most relevant passages.

    The passages are registered in the turn's source registry, which is what grounds
    their numbers and yields the response's sources, so the reply is not added to
    ``tool_outputs``.

    :param query: What to search for, in the user's own words.
    :param runtime: Injected request context (hidden from the model).
    :return: The passages wrapped in ``<docs>...</docs>``, numbered for citation, or
        the ``no_result:`` or ``unavailable:`` line.
    """
    ctx = runtime.context
    try:
        chunks = await ctx.retriever.search(query)
    except UNAVAILABLE_ERRORS as exc:
        return _unavailable("search_docs", exc)
    if not chunks:
        return _NO_PASSAGES
    entries = [format_excerpt(ctx.sources.add(chunk), chunk) for chunk in chunks]
    return "<docs>\n" + "\n\n".join(entries) + "\n</docs>"


@tool(description=_LIST_MY_PROJECTS_DESCRIPTION)
async def list_my_projects(runtime: ToolRuntime[AssistantContext]) -> str:
    """List the projects the current user is a member of.

    :param runtime: Injected request context (hidden from the model).
    :return: The caller's projects as a data block, or the ``no_result:`` or
        ``unavailable:`` line.
    """
    ctx = runtime.context
    try:
        projects = await ctx.client.list_projects()
    except _BACKEND_FAILURES as exc:
        return _reply(ctx, _unavailable("list_my_projects", exc))
    if not projects:
        return _reply(ctx, _NO_PROJECTS)
    return _reply(ctx, render_project_list(projects))


@tool(description=_GET_PROJECT_DESCRIPTION)
async def get_project(project_id: str, runtime: ToolRuntime[AssistantContext]) -> str:
    """Get the name, description, and scale of one of the user's own projects.

    :param project_id: The project's id.
    :param runtime: Injected request context (hidden from the model).
    :return: The project's details as a data block, or the ``not_found:`` or
        ``unavailable:`` line.
    """
    ctx = runtime.context
    try:
        project = await ctx.client.get_project(project_id)
    except AssistantNotFoundError:
        return _reply(ctx, _NOT_FOUND)
    except _BACKEND_FAILURES as exc:
        return _reply(ctx, _unavailable("get_project", exc))
    return _reply(ctx, render_project(project))


@tool(description=_GET_PROJECT_RESULT_DESCRIPTION)
async def get_project_result(project_id: str, runtime: ToolRuntime[AssistantContext]) -> str:
    """Get the calculated BeCoMe result for one of the user's own projects.

    :param project_id: The project's id.
    :param runtime: Injected request context (hidden from the model).
    :return: The result as a data block, or the ``not_found:``, ``no_result:`` or
        ``unavailable:`` line.
    """
    ctx = runtime.context
    try:
        result = await ctx.client.get_result(project_id)
    except AssistantNotFoundError:
        return _reply(ctx, _NOT_FOUND)
    except _BACKEND_FAILURES as exc:
        return _reply(ctx, _unavailable("get_project_result", exc))
    if result is None:
        return _reply(ctx, _NO_RESULT_YET)
    return _reply(ctx, render_context_block([], result))


@tool(description=_GET_PROJECT_OPINIONS_DESCRIPTION)
async def get_project_opinions(project_id: str, runtime: ToolRuntime[AssistantContext]) -> str:
    """Get the individual expert opinions submitted to one of the user's own projects.

    :param project_id: The project's id.
    :param runtime: Injected request context (hidden from the model).
    :return: The opinions as a data block, or the ``not_found:``, ``no_result:`` or
        ``unavailable:`` line.
    """
    ctx = runtime.context
    try:
        opinions = await ctx.client.get_opinions(project_id)
    except AssistantNotFoundError:
        return _reply(ctx, _NOT_FOUND)
    except _BACKEND_FAILURES as exc:
        return _reply(ctx, _unavailable("get_project_opinions", exc))
    if not opinions:
        return _reply(ctx, _NO_OPINIONS)
    return _reply(ctx, render_opinions(opinions))


ASSISTANT_TOOLS: list[BaseTool] = [
    search_docs,
    list_my_projects,
    get_project,
    get_project_result,
    get_project_opinions,
]
