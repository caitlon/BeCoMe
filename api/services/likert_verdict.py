"""Derive the Likert agreement verdict from a project and its stored compromise.

The verdict used to be stored alongside the calculation, and that is what made it
possible for it to disagree with the project: editing a scale rewrote the project row
and left the saved verdict untouched, so a percentage or a budget kept a sentence like
"Rather disagree" attached to it. A migration cleaned the rows once, and the code went
straight on producing them again.

It is derived here instead, on every read. Nothing about that is expensive: the verdict
is a pure function of two things the database already holds, the project's scale and the
compromise triple, and it needs no expert opinions at all. A value computed from stored
data and then stored again is a cache, and a cache with no invalidation is a defect
waiting for its next writer.
"""

from dataclasses import dataclass

from api.db.models import Project
from api.services.protocols import LikertInterpreterProtocol
from src.interpreters.likert_interpreter import LikertDecisionInterpreter
from src.models.fuzzy_number import FuzzyTriangleNumber

# The agreement scale runs 0 to 100. Constants rather than parameters because nothing in
# the project ever passed anything else, and a knob nobody turns reads as a decision
# somebody might have made differently.
LIKERT_SCALE_MIN = 0.0
LIKERT_SCALE_MAX = 100.0

_INTERPRETER: LikertInterpreterProtocol = LikertDecisionInterpreter()


@dataclass(frozen=True)
class LikertVerdict:
    """The agreement reading of a compromise, for a project measured on that scale.

    :ivar value: Closest Likert point, one of 0, 25, 50, 75, 100
    :ivar decision: Human-readable text for that point
    """

    value: int
    decision: str


def is_likert_scale(project: Project) -> bool:
    """Check whether a project uses the standard, unitless Likert agreement scale.

    Agreement is dimensionless, so the 0-100 range alone does not mark a project as
    Likert: a percentage or a budget in billions can share that range without expressing
    agreement. Requiring an empty ``scale_unit`` rules those out. A whitespace-only unit
    counts as empty, because the strings arrive from a text field.

    :param project: Project to check
    :return: True if the scale is the standard 0-100 range and carries no unit
    """
    return (
        project.scale_min == LIKERT_SCALE_MIN
        and project.scale_max == LIKERT_SCALE_MAX
        and not project.scale_unit.strip()
    )


def derive_verdict(
    project: Project, lower: float, peak: float, upper: float
) -> LikertVerdict | None:
    """Read the compromise as an agreement verdict, when the project is on that scale.

    Takes the three bounds rather than a domain object because every caller has them as
    plain columns off the stored result.

    :param project: Project the compromise belongs to
    :param lower: Lower bound of the best compromise
    :param peak: Peak of the best compromise
    :param upper: Upper bound of the best compromise
    :return: The verdict, or None when the project is not measured on an agreement scale
    """
    if not is_likert_scale(project):
        return None

    decision = _INTERPRETER.interpret(
        FuzzyTriangleNumber(lower_bound=lower, peak=peak, upper_bound=upper)
    )
    return LikertVerdict(value=decision.likert_value, decision=decision.decision_text)
