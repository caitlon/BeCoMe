"""Read Δmax against the width of a project's scale, on every read.

Δmax is an absolute distance, so on its own it says nothing: 6 is six percent of a
0-100 scale and 0.06 percent of a 0-10000 one, and those are not the same finding.
The interface has always divided by the range and labelled the result, and this is
that rule, moved to where both readers of it can reach.

It lived in ``ResultsSection.tsx`` alone, which meant the PDF export could not show
the same badge as the page that produced it -- and that a change to either threshold
would have moved one and not the other, silently, with no test going red. Deriving
it here follows :mod:`api.services.likert_verdict`: a pure function of what the
database already holds, computed on read and never stored, because a value computed
from stored data and written back is a cache without invalidation.
"""

from enum import StrEnum

from api.db.models import Project

# Shares of the scale, not of the value. Both bounds are inclusive, which is how the
# interface has read them since the thresholds were introduced.
_HIGH_SHARE = 0.20
_MODERATE_SHARE = 0.40


class AgreementLevel(StrEnum):
    """How closely the mean and the median of a panel landed together."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


def derive_agreement(project: Project, max_error: float) -> AgreementLevel:
    """Read a compromise's Δmax as an agreement level for that project's scale.

    :param project: Project the compromise belongs to, for its scale bounds.
    :param max_error: Δmax of the compromise, in the units of that scale.
    :return: The level the interface labels this error with.
    :raises ValueError: If Δmax is negative. Three layers above guarantee it is not
        -- the domain model, the schema and a database constraint -- so reaching this
        means one of them broke. A negative value would otherwise pass the first
        threshold and report the widest possible disagreement as high agreement,
        which is the one failure here worth refusing to guess about.
    """
    if max_error < 0:
        msg = f"max_error must not be negative, got {max_error}"
        raise ValueError(msg)
    share = max_error / (project.scale_max - project.scale_min)
    if share <= _HIGH_SHARE:
        return AgreementLevel.HIGH
    if share <= _MODERATE_SHARE:
        return AgreementLevel.MODERATE
    return AgreementLevel.LOW
