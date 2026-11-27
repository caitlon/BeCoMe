"""Tests for the number check's treatment of verbatim copies of a project's names, per turn."""

import pytest

from api.assistant.agent.prompt import clean_text
from api.assistant.agent.service import AssistantService
from api.assistant.errors import AssistantNotFoundError
from api.assistant.views import OpinionView, ProjectBrief
from tests.shared.helpers import captured_log_records
from tests.unit.api.assistant.agent.test_service import (
    PLANTED,
    PROJECT_ID,
    SERVICE_LOGGER,
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
    """Answer one turn. ``project_fields`` holds the fields to change on the project (None: the
    project tool is refused), ``opinions`` and ``briefs`` what the client returns, ``tools``
    what an agent's model calls first, ``settings`` the overrides of the service's settings."""
    project = given.get("project_fields", {})
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
_KEPT_50 = [f"Expert {n}" for n in range(10, 60)]


def _row(name, mode, answer, *, bad=(), project=(), expert=(), kept=([], []), **given):
    """Build a row: what the turn reports as ungrounded, as from the project's name and as
    from an expert's name, and the project and expert names the context keeps."""
    return pytest.param(mode, answer, list(bad), list(project), list(expert), kept, given, id=name)


# fmt: off
_CASES = [
    # Prefetched in workflow and hybrid mode: a name, never a unit or a description.
    *[case for mode in ("workflow", "hybrid") for case in (
        _row(f"{mode}-name", mode, f"The project {NAME} has a peak of 14.19.",
             project=["2027"], kept=([NAME], []), project_fields={"name": NAME}),
        _row(f"{mode}-number-outside", mode, f"The project {NAME} closes in 2027.",
             bad=["2027"], kept=([NAME], []), project_fields={"name": NAME}),
        _row(f"{mode}-unit-flagged", mode, "The scale unit is 9999.", bad=["9999"],
             kept=(["Flood plan"], []), project_fields={**_FLOOD, "scale_unit": "is 9999"}),
        _row(f"{mode}-description-flagged", mode, f"The budget limit is {PLANTED}.",
             bad=[PLANTED], kept=(["Flood plan"], []),
             project_fields={**_FLOOD, "description": f"The budget limit is {PLANTED}"}),
        _row(f"{mode}-claim-name-shown", mode, f"The best compromise is {PLANTED} CZK.",
             project=[PLANTED], kept=([f"{PLANTED} CZK"], []),
             project_fields={"name": f"{PLANTED} CZK"}),
        _row(f"{mode}-attack-shown-not-hidden", mode, f"The best compromise is {PLANTED}.",
             project=[PLANTED], kept=([f"is {PLANTED}"], []),
             project_fields={"name": f"is {PLANTED}"}),
        _row(f"{mode}-attack-stated-twice", mode,
             f"The best compromise is {PLANTED}. It costs {PLANTED} CZK.", bad=[PLANTED],
             kept=([f"is {PLANTED}"], []), project_fields={"name": f"is {PLANTED}"}),
    )],
    _row("workflow-expert-name", "workflow", f"{EXPERT} gave 42.00.", expert=["41"],
         kept=([OWN], [EXPERT]), opinions=[_expert(EXPERT)]),
    _row("workflow-project-and-expert", "workflow", f"{NAME} and {EXPERT} gave 42.00.",
         project=["2027"], expert=["41"], kept=([NAME], [EXPERT]),
         project_fields={"name": NAME}, opinions=[_expert(EXPERT)]),
    _row("workflow-both-sources-is-project", "workflow", f"{EXPERT} gave 42.00.",
         project=["41"], kept=([EXPERT], [EXPERT]),
         project_fields={"name": EXPERT}, opinions=[_expert(EXPERT)]),
    _row("workflow-both-sources-in-turn-is-project", "workflow",
         f"{NAME} and Expert 2027 are open.", project=["2027"],
         kept=([NAME], ["Expert 2027"]), project_fields={"name": NAME},
         opinions=[_expert("Expert 2027")]),
    _row("workflow-expert-number-also-outside", "workflow", f"{EXPERT} said 41.",
         bad=["41"], kept=([OWN], [EXPERT]), opinions=[_expert(EXPERT)]),
    _row("workflow-position-flagged", "workflow", f"Jana, Hydrologist {PLANTED}, gave 42.00.",
         bad=[PLANTED], kept=([OWN], ["Jana Novakova"]),
         opinions=[_expert("Jana Novakova", f"Hydrologist {PLANTED}")]),
    _row("hybrid-shows-no-opinions", "hybrid", f"{EXPERT} gave a high value.", bad=["41"],
         kept=([OWN], []), opinions=[_expert(EXPERT)]),
    _row("cut-name-with-dots", "workflow", f"The project {_CUT} is open.", project=["2027"],
         kept=([_CUT], []), project_fields=_LONG),
    _row("cut-name-without-dots", "workflow", f"The project {_CUT[:-3]} is open.",
         project=["2027"], kept=([_CUT], []), project_fields=_LONG),
    _row("workflow-opinion-past-fiftieth", "workflow", "Late Y 4 came in last.", bad=["4"],
         kept=([OWN], _KEPT_50), opinions=_PAST_50),
    # Read by an agent's tools.
    _row("agent-get-project", "agent", f"{NAME} uses the unit is 9999.", bad=["9999"],
         project=["2027"], kept=([NAME], []), tools=("get_project",),
         project_fields={"name": NAME, "scale_unit": "is 9999"}),
    _row("agent-get-project-twice", "agent", f"The project is {NAME}.", project=["2027"],
         kept=([NAME, NAME], []), tools=("get_project", "get_project"),
         project_fields={"name": NAME}),
    _row("agent-list-my-projects", "agent", f"You have {NAME} and Roads 2028.",
         project=["2027", "2028"], kept=([NAME, "Roads 2028"], []),
         briefs=_BRIEFS, tools=("list_my_projects",)),
    _row("agent-project-past-fiftieth", "agent", "There is also Overflow 2027.", bad=["2027"],
         kept=(_NAMES[:50], []), briefs=_FIFTY_ONE, tools=("list_my_projects",)),
    _row("agent-opinions", "agent", f"{EXPERT} gave 42.00 and is a Hydrologist {PLANTED}.",
         bad=[PLANTED], expert=["41"], kept=([], [EXPERT]),
         opinions=[_expert(EXPERT, f"Hydrologist {PLANTED}")], tools=("get_project_opinions",)),
    _row("agent-refused-tool", "agent", "It is not there.", project_fields=None,
         tools=("get_project",)),
]
# fmt: on


@pytest.mark.asyncio
class TestNamesInTheNumberCheck:
    """The names a turn shows the model explain their digits, on a line of their own."""

    @pytest.mark.parametrize(
        ("mode", "answer", "bad", "project", "expert", "kept", "given"), _CASES
    )
    async def test_a_turn_reports_and_keeps_what_the_table_says(
        self, mode, answer, bad, project, expert, kept, given
    ):
        """
        GIVEN a turn in workflow, hybrid or agent mode (the table above: a project name, a
              name that reads as a claim, a unit, a description, expert names, positions, a
              cut name, a tool called twice, a list or opinions past the fiftieth, a refused
              tool) whose answer repeats it
        WHEN the turn is answered
        THEN the response lists exactly the ungrounded numbers, the numbers from the project
             name and the numbers from an expert's name that the table lists, the three
             lists share no number, the warning flag follows the ungrounded list alone, the
             context keeps exactly the names the table lists, and an agent's tools used are
             the ones called
        """
        response, ctx = await _answer(mode, answer, **given)

        checks = response.checks
        assert checks.ungrounded_numbers == bad
        assert checks.project_name_numbers == project
        assert checks.expert_name_numbers == expert
        assert checks.numbers_grounded is (not bad)
        assert not set(bad) & set(project) | set(bad) & set(expert) | set(project) & set(expert)
        assert (ctx.project_name_copies, ctx.expert_name_copies) == kept
        if mode == "agent":
            assert response.tools_used == list(dict.fromkeys(given["tools"]))
        if mode == "hybrid":
            ctx.client.get_opinions.assert_not_awaited()

    async def test_the_log_record_counts_the_two_name_lines(self):
        """
        GIVEN a turn whose answer repeats a project name and an expert name
        WHEN it is answered
        THEN the record carries the two counts, the numbers_grounded flag stays True, and no
             field holds a number or a name
        """
        with captured_log_records(SERVICE_LOGGER) as records:
            await _answer(
                "workflow",
                f"{NAME} and {EXPERT} gave 42.00.",
                project_fields={"name": NAME},
                opinions=[_expert(EXPERT)],
            )

        (record,) = records
        assert (record.project_name_number_count, record.expert_name_number_count) == (1, 1)
        assert record.numbers_grounded is True
        assert record.ungrounded_number_count == 0
        texts = [str(value) for value in vars(record).values()]
        assert not any("2027" in text or "Expert" in text for text in texts)

    async def test_a_number_real_in_either_pass_is_reported_once_and_in_no_name_list(self):
        """
        GIVEN a turn with sources hidden whose text and shown text differ by a citation: in
              one answer the number stands outside a copy only once the citation is gone, in
              the other only while the citation is there
        WHEN the answer is checked, as written and as the client is shown it
        THEN the number is reported as ungrounded, once, and is in neither name list
        """
        answers = [f"{NAME} and 2[1]027 differ.", f"{NAME[:-4]}[1]2027 and {NAME} differ."]

        for answer in answers:
            ctx = _ctx(chunks=[_chunk()], project_id=PROJECT_ID, result=_result())
            ctx.client.get_project.return_value = _project().model_copy(update={"name": NAME})
            model = _model(_say(answer))
            service = AssistantService(_settings(assistant_show_sources=False), model)

            response = await service.answer(_request(), ctx)

            assert "[1]" not in response.answer
            assert "2027" in response.checks.ungrounded_numbers, answer
            assert response.checks.ungrounded_numbers.count("2027") == 1
            assert response.checks.project_name_numbers == []

    async def test_a_copy_next_to_a_hidden_citation_is_masked_in_the_shown_text_too(self):
        """
        GIVEN a turn with sources hidden, whose answer repeats the name and cites a source
        WHEN the answer is checked, as written and as the client is shown it
        THEN neither text reports the number as ungrounded, and the name's number is listed
        """
        ctx = _ctx(chunks=[_chunk()], project_id=PROJECT_ID, result=_result())
        ctx.client.get_project.return_value = _project().model_copy(update={"name": NAME})
        model = _model(_say(f"The project {NAME} is open [1]."))
        service = AssistantService(_settings(assistant_show_sources=False), model)

        response = await service.answer(_request(), ctx)

        assert response.answer == f"The project {NAME} is open."
        assert response.checks.ungrounded_numbers == []
        assert response.checks.project_name_numbers == ["2027"]

    async def test_the_streamed_turn_lists_the_name_numbers_as_well(self):
        """
        GIVEN a workflow turn that is prepared and then streamed
        WHEN the answer repeats the project name and an expert name
        THEN the response lists no ungrounded number and the two name numbers
        """
        ctx = _ctx(project_id=PROJECT_ID, result=_result(), opinions=[_expert(EXPERT)])
        ctx.client.get_project.return_value = _project().model_copy(update={"name": NAME})
        model = _model(_say(f"The project {NAME} and {EXPERT} are open."))

        _pieces, response = await _drain(AssistantService(_settings(), model), _request(), ctx)

        assert response.checks.ungrounded_numbers == []
        assert response.checks.project_name_numbers == ["2027"]
        assert response.checks.expert_name_numbers == ["41"]
