"""Tests for the number check's treatment of verbatim copies of a project's names, per turn."""

from unittest.mock import patch

import pytest

from api.assistant.agent import service as service_module
from api.assistant.agent.checks import find_ungrounded_numbers
from api.assistant.agent.prompt import clean_text
from api.assistant.agent.service import AssistantService
from api.assistant.errors import AssistantNotFoundError
from api.assistant.views import OpinionView, ProjectBrief
from tests.unit.api.assistant.agent.test_service import (
    PLANTED,
    PROJECT_ID,
    _call,
    _chunk,
    _ctx,
    _drain,
    _model,
    _project,
    _request,
    _result,
    _say,
    _settings,
)

NAME = "Budget 2027"
EXPERT = "Expert 41"
OWN = _project().name
_CUT = clean_text(f"{NAME} " + "flood works " * 20, 120)
assert _CUT.endswith("...")
_NAMES = [f"Alpha project {index}" for index in range(1, 51)] + ["Overflow 2027"]


def _briefs(names: list[str]) -> list[ProjectBrief]:
    return [
        ProjectBrief(
            id=f"00000000-0000-4000-8000-{n:012d}", name=x, role="expert", is_example=False
        )
        for n, x in enumerate(names, 1)
    ]


_BRIEFS, _FIFTY_ONE = _briefs([NAME, "Roads 2028"]), _briefs(_NAMES)


def _expert(name: str, position: str = "Hydrologist") -> OpinionView:
    """Build an opinion whose four values are 37, 42, 47 and 42."""
    return OpinionView(
        expert_name=name, position=position, lower_bound=37, peak=42, upper_bound=47, centroid=42
    )


async def _answer(mode: str, answer: str, **given):
    """Answer one turn. ``project`` holds the fields to change on the project (None: the
    project tool is refused), ``opinions`` and ``briefs`` what the client returns, ``tools``
    what an agent's model calls first, ``settings`` the overrides of the service's settings."""
    project = given.get("project", {})
    ctx = _ctx(
        project_id=None if mode == "agent" else PROJECT_ID,
        result=_result(),
        opinions=given.get("opinions", []),
    )
    if project is None:
        ctx.client.get_project.side_effect = AssistantNotFoundError("no such project")
    else:
        ctx.client.get_project.return_value = _project().model_copy(update=project)
    ctx.client.list_projects.return_value = given.get("briefs", [])
    steps = [
        _call(tool, index, **({} if tool == "list_my_projects" else {"project_id": PROJECT_ID}))
        for index, tool in enumerate(given.get("tools", ()), 1)
    ]
    service = AssistantService(
        _settings(mode, **given.get("settings", {})), _model(*steps, _say(answer))
    )
    return await service.answer(_request(), ctx), ctx


_FLOOD = {"name": "Flood plan"}
_LONG = {"name": f"{NAME} " + "flood works " * 20}
_PAST_50 = [_expert(f"Expert {n}") for n in range(10, 60)] + [_expert("Late Y 4")]
# (id, mode, answer, reported numbers, kept copies, what the turn is given)
# fmt: off
_CASES = [
    # Prefetched in workflow and hybrid mode: a name, never a unit or a description.
    *[case for mode in ("workflow", "hybrid") for case in (
        (f"{mode}-name", mode, f"The project {NAME} has a peak of 14.19.", [], [NAME],
         {"project": {"name": NAME}}),
        (f"{mode}-number-outside", mode, f"The project {NAME} closes in 2027.", ["2027"], [NAME],
         {"project": {"name": NAME}}),
        (f"{mode}-unit-flagged", mode, "The scale unit is 9999.", ["9999"], ["Flood plan"],
         {"project": {**_FLOOD, "scale_unit": "is 9999"}}),
        (f"{mode}-description-flagged", mode, f"The budget limit is {PLANTED}.", [PLANTED],
         ["Flood plan"], {"project": {**_FLOOD, "description": f"The budget limit is {PLANTED}"}}),
    )],
    ("workflow-expert-name", "workflow", f"{EXPERT} gave 42.00.", [], [OWN, EXPERT],
     {"opinions": [_expert(EXPERT)]}),
    ("workflow-position-flagged", "workflow", f"Jana, Hydrologist {PLANTED}, gave 42.00.",
     [PLANTED], [OWN, "Jana Novakova"],
     {"opinions": [_expert("Jana Novakova", f"Hydrologist {PLANTED}")]}),
    ("hybrid-shows-no-opinions", "hybrid", f"{EXPERT} gave a high value.", ["41"], [OWN],
     {"opinions": [_expert(EXPERT)]}),
    ("cut-name-with-dots", "workflow", f"The project {_CUT} is open.", [], [_CUT],
     {"project": _LONG}),
    ("cut-name-without-dots", "workflow", f"The project {_CUT[:-3]} is open.", [], [_CUT],
     {"project": _LONG}),
    ("workflow-opinion-past-fiftieth", "workflow", "Late Y 4 came in last.", ["4"],
     [OWN, *[f"Expert {n}" for n in range(10, 60)]], {"opinions": _PAST_50}),
    # Read by an agent's tools.
    ("agent-get-project", "agent", f"{NAME} uses the unit is 9999.", ["9999"], [NAME],
     {"project": {"name": NAME, "scale_unit": "is 9999"}, "tools": ("get_project",)}),
    ("agent-get-project-twice", "agent", f"The project is {NAME}.", [], [NAME, NAME],
     {"project": {"name": NAME}, "tools": ("get_project", "get_project")}),
    ("agent-list-my-projects", "agent", f"You have {NAME} and Roads 2028.", [],
     [NAME, "Roads 2028"], {"briefs": _BRIEFS, "tools": ("list_my_projects",)}),
    ("agent-project-past-fiftieth", "agent", "There is also Overflow 2027.", ["2027"], _NAMES[:50],
     {"briefs": _FIFTY_ONE, "tools": ("list_my_projects",)}),
    ("agent-opinions", "agent", f"{EXPERT} gave 42.00 and is a Hydrologist {PLANTED}.", [PLANTED],
     [EXPERT], {"opinions": [_expert(EXPERT, f"Hydrologist {PLANTED}")],
                "tools": ("get_project_opinions",)}),
    ("agent-refused-tool", "agent", "It is not there.", [], [],
     {"project": None, "tools": ("get_project",)}),
]
# fmt: on


@pytest.mark.asyncio
class TestNamesInTheNumberCheck:
    """The names a turn shows the model are copies; nothing else it shows is."""

    @pytest.mark.parametrize(
        ("mode", "answer", "ungrounded", "copies", "given"),
        [pytest.param(*case[1:], id=case[0]) for case in _CASES],
    )
    async def test_a_turn_reports_and_keeps_what_the_table_says(
        self, mode, answer, ungrounded, copies, given
    ):
        """
        GIVEN a turn in workflow, hybrid or agent mode (the table above: a project name, a
              unit, a description, expert names, positions, a cut name, a tool called twice,
              a list or opinions past the fiftieth, a refused tool) whose answer repeats it
        WHEN the turn is answered
        THEN the response reports exactly the numbers the table lists, the context keeps
             exactly the names the table lists, and an agent's tools used are the ones called
        """
        response, ctx = await _answer(mode, answer, **given)

        assert response.checks.ungrounded_numbers == ungrounded
        assert response.checks.numbers_grounded is (not ungrounded)
        assert ctx.text_copies == copies
        if mode == "agent":
            assert response.tools_used == list(dict.fromkeys(given["tools"]))
        if mode == "hybrid":
            ctx.client.get_opinions.assert_not_awaited()

    async def test_a_name_written_as_a_claim_passes_when_copied_and_not_when_restated(self):
        """
        GIVEN a project named "Best compromise 99"
        WHEN the answer repeats the name as its own sentence, and in another turn restates 99
        THEN the first reports nothing, the residual risk the check's docstring names, and
             the second reports 99
        """
        name = "Best compromise 99"
        answers = [f"{name}.", f"The project {name}, and 99 is the figure."]

        reported = [
            (await _answer("workflow", answer, project={"name": name}))[0].checks.ungrounded_numbers
            for answer in answers
        ]

        assert reported == [[], ["99"]]

    async def test_a_copy_next_to_a_hidden_citation_is_masked_in_the_shown_text_too(self):
        """
        GIVEN a turn with sources hidden, whose answer repeats the name and cites a source
        WHEN the answer is checked, as written and as the client is shown it
        THEN neither pass reports the number, and both receive the copies
        """
        ctx = _ctx(chunks=[_chunk()], project_id=PROJECT_ID, result=_result())
        ctx.client.get_project.return_value = _project().model_copy(update={"name": NAME})
        model = _model(_say(f"The project {NAME} is open [1]."))
        service = AssistantService(_settings(assistant_show_sources=False), model)

        with patch.object(
            service_module, "find_ungrounded_numbers", wraps=find_ungrounded_numbers
        ) as spy:
            response = await service.answer(_request(), ctx)

        assert "[1]" not in response.answer
        assert response.checks.ungrounded_numbers == []
        assert len(spy.call_args_list) == 2
        assert all(call.kwargs["copies"] == [NAME] for call in spy.call_args_list)

    async def test_the_copies_are_not_part_of_the_grounding(self):
        """
        GIVEN a turn with a copy
        WHEN the answer is checked
        THEN the grounding texts hold no copy, and the copies go as a keyword
        """
        with patch.object(
            service_module, "find_ungrounded_numbers", wraps=find_ungrounded_numbers
        ) as spy:
            await _answer("workflow", "Fine.", project={"name": NAME})

        assert NAME not in spy.call_args.args[1]
        assert spy.call_args.kwargs == {"copies": [NAME]}

    async def test_the_streamed_turn_masks_the_copy_as_well(self):
        """
        GIVEN a workflow turn that is prepared and then streamed
        WHEN the answer repeats the project name
        THEN the response reports no number
        """
        ctx = _ctx(project_id=PROJECT_ID, result=_result())
        ctx.client.get_project.return_value = _project().model_copy(update={"name": NAME})
        model = _model(_say(f"The project {NAME} is open."))

        _pieces, response = await _drain(AssistantService(_settings(), model), _request(), ctx)

        assert response.checks.ungrounded_numbers == []
