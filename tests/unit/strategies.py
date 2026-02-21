"""Hypothesis strategies for generating BeCoMe domain objects."""

from hypothesis import strategies as st

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

_FINITE_FLOATS = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


@st.composite
def fuzzy_numbers(draw: st.DrawFn) -> FuzzyTriangleNumber:
    """Generate a valid FuzzyTriangleNumber with lower <= peak <= upper.

    Draws three finite floats from [-1e6, 1e6] and sorts them
    to guarantee the triangular constraint.
    """
    values = draw(st.lists(_FINITE_FLOATS, min_size=3, max_size=3))
    a, c, b = sorted(values)
    return FuzzyTriangleNumber(lower_bound=a, peak=c, upper_bound=b)


@st.composite
def expert_opinions(
    draw: st.DrawFn,
    min_size: int = 1,
    max_size: int = 15,
) -> list[ExpertOpinion]:
    """Generate a list of ExpertOpinion instances with unique IDs.

    :param min_size: minimum number of experts (default 1)
    :param max_size: maximum number of experts (default 15)
    """
    count = draw(st.integers(min_value=min_size, max_value=max_size))
    return [
        ExpertOpinion(expert_id=f"E{i + 1}", opinion=draw(fuzzy_numbers())) for i in range(count)
    ]


@st.composite
def identical_expert_opinions(
    draw: st.DrawFn,
    min_size: int = 2,
    max_size: int = 15,
) -> list[ExpertOpinion]:
    """Generate a list of ExpertOpinion instances sharing the same fuzzy number.

    :param min_size: minimum number of experts (default 2)
    :param max_size: maximum number of experts (default 15)
    """
    fn = draw(fuzzy_numbers())
    count = draw(st.integers(min_value=min_size, max_value=max_size))
    return [ExpertOpinion(expert_id=f"E{i + 1}", opinion=fn) for i in range(count)]
