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
descriptions, expert names) goes through
:func:`~api.assistant.agent.prompt.clean_text` before it enters a reply, so it cannot
close a ``<project_data>`` block or start a line of its own. That includes an expert's
position, which an opinions row shows after the name.

The functions that write a data block (``render_project``, ``render_project_list``,
``render_opinions``) are public: the chat service calls the same ones for what it
fetches ahead of the model, so a fact is written one way wherever the model meets it.
"""

import logging
import re
from collections.abc import Sequence

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool

from api.assistant.agent.context import AssistantContext
from api.assistant.agent.masking import (
    EXPERT_LABEL,
    ROW_HEAD_END,
    ROW_MARK,
    TurnRoster,
    expert_label,
    opinion_head,
)
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
# small in a 16k-token window, so an expert's name (see ``EXPERT_LIMIT``) is the tightest.
_NAME_LIMIT = 120
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


# The count line that opens an opinions block, and the shape of one opinion row, written
# once so that the renderer and the mask applied to LangSmith traces cannot drift apart:
# the mask reads exactly what the renderer writes. The row's literals contain no regex
# metacharacter, so the template is used as a pattern as it stands.
_OPINION_COUNT_PREFIX = "Number of opinions: "
_OPINION_VALUES_TEMPLATE = "lower={}, peak={}, upper={}, centroid={}"
_OPINION_COUNT_LINE = re.compile(_OPINION_COUNT_PREFIX + r"\d+")
# The pattern is applied with ``fullmatch`` and the fixed tail is anchored at the end of the
# line, so the split between head (name and position) and tail is unique and a head that
# itself contains the tail is masked whole.
_OPINION_ROW = re.compile(
    re.escape(ROW_MARK)
    + "(?P<head>.*)"
    + re.escape(ROW_HEAD_END)
    + _OPINION_VALUES_TEMPLATE.format(*[r"-?\d+\.\d{2}"] * 4)
)


def render_opinions(opinions: Sequence[OpinionView]) -> str:
    """Render a project's expert opinions as a data block.

    The block has a count line, then at most 50 opinions, then ``... and N more
    opinions`` when there are more. A row is the expert's name, the position in parentheses
    when there is one, and the four numbers.

    :param opinions: The project's opinions.
    :return: The block.
    """
    lines = [f"{_OPINION_COUNT_PREFIX}{len(opinions)}"]
    for opinion in opinions[:_MAX_OPINIONS]:
        values = _OPINION_VALUES_TEMPLATE.format(
            format_number(opinion.lower_bound),
            format_number(opinion.peak),
            format_number(opinion.upper_bound),
            format_number(opinion.centroid),
        )
        lines.append(f"{ROW_MARK}{opinion_head(opinion)}{ROW_HEAD_END}{values}")
    if len(opinions) > _MAX_OPINIONS:
        lines.append(f"... and {len(opinions) - _MAX_OPINIONS} more opinions")
    return _block(lines)


# What ends a line. A text reaches the mask either as it was written, with real newlines, or
# as ``repr(exc)`` and the like, where each newline is the two characters backslash and ``n``.
# The second form also doubles every backslash, so a doubled backslash is a token of its own:
# consumed first, it keeps a name that holds a typed backslash and ``n`` in one piece.
_REAL_LINE_BREAK = re.compile(r"(\n)")
_ESCAPED_LINE_BREAK = re.compile(r"(\\\\|\\n)")


def _split_lines(text: str, line_break: re.Pattern[str]) -> tuple[list[str], list[str]]:
    """Cut a text into lines and keep the breaks between them.

    :param text: The text; the break is the pattern's one capturing group.
    :param line_break: The pattern that finds a line break, a doubled backslash included
        as a token that is not one.
    :return: The lines, and the break that follows each of them but the last.
    """
    lines = [""]
    breaks: list[str] = []
    for index, piece in enumerate(line_break.split(text)):
        if index % 2 == 0 or piece == "\\\\":
            lines[-1] += piece
        else:
            breaks.append(piece)
            lines.append("")
    return lines, breaks


def _label_rows(lines: list[str], roster: TurnRoster | None) -> None:
    """Replace the name of every row of an opinions block in the lines, in place.

    :param lines: The lines of a text.
    :param roster: The turn's participants, or None to number the rows of each block.
    """
    row_number = 0
    in_block = False
    for index, line in enumerate(lines):
        if _OPINION_COUNT_LINE.fullmatch(line):
            in_block, row_number = True, 0
            continue
        row = _OPINION_ROW.fullmatch(line) if in_block else None
        if row is None:
            in_block = False
            continue
        row_number += 1
        if not EXPERT_LABEL.fullmatch(row["head"]):
            label = expert_label(row_number) if roster is None else roster.label_for(row["head"])
            lines[index] = ROW_MARK + label + line[row.end("head") :]


def _mask_lines(text: str, line_break: re.Pattern[str], roster: TurnRoster | None) -> str:
    """Mask the opinions blocks of a text whose lines end with the given break.

    :param text: The text; the break is the pattern's one capturing group.
    :param line_break: The pattern that finds a line break, a doubled backslash included
        as a token that is not one.
    :param roster: The turn's participants, or None to number the rows of each block.
    :return: The text with each block's names replaced, every break as it was.
    """
    lines, breaks = _split_lines(text, line_break)
    _label_rows(lines, roster)
    joined = [lines[0]]
    for line_break_text, line in zip(breaks, lines[1:], strict=True):
        joined += [line_break_text, line]
    return "".join(joined)


def mask_opinion_rows(text: str, roster: TurnRoster | None = None) -> str:
    """Replace the expert names in every opinions block of a text with ``Expert N`` labels.

    A block is found by its shape alone, the count line :func:`render_opinions` writes and
    the rows that follow it, so no list of names is needed. Every row is masked, the
    asker's own included, because the block does not say which row is theirs. The numbers
    stay. A row whose name is already ``Expert N`` is left as it is, so that this mask never
    renumbers a label given earlier. With a roster this mask runs before
    :func:`~api.assistant.agent.masking.mask_participants`, and gives a known expert's row
    the roster's label itself. A row-shaped line that is not directly under
    a count line is left as it is. A block is found whether its lines end with a newline or
    with the two characters backslash and ``n``, as in ``repr(exc)``; the text is read once
    for each form, so a name that holds a typed backslash and ``n`` cannot cut its row in two.

    :param text: Any text; one that holds no opinions block comes back unchanged.
    :param roster: The turn's participants. With it, a row of an expert the roster has not
        met is added to it and takes the next free label, so it never shares a label with
        an expert the roster knows; without it, rows are numbered from 1 within the block.
    :return: The text with each block's names replaced.
    """
    if _OPINION_COUNT_PREFIX not in text:
        return text
    return _mask_lines(_mask_lines(text, _REAL_LINE_BREAK, roster), _ESCAPED_LINE_BREAK, roster)


def mask_opinion_names(text: str) -> str:
    """Replace the expert names in every opinions block of a text, numbering rows from 1.

    This is :func:`mask_opinion_rows` without a roster, the one-argument form the LangSmith
    client's anonymizer calls.

    :param text: Any text; one that holds no opinions block comes back unchanged.
    :return: The text with each block's names replaced, numbered from 1 within the block.
    """
    return mask_opinion_rows(text)


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
    ctx.roster.add(opinions)
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
