"""Unit tests for deriving the Likert agreement verdict.

These moved here from the calculation service, which used to compute the verdict and
store it alongside the result. It is derived on read now, so the rules that decide
whether a project is measured on an agreement scale belong with the derivation.
"""

from uuid import uuid4

import pytest

from api.db.models import Project
from api.services.likert_verdict import LikertVerdict, derive_verdict, is_likert_scale


def _project(*, scale_min: float = 0.0, scale_max: float = 100.0, scale_unit: str = "") -> Project:
    """Build a project with the given scale and nothing else that matters here."""
    return Project(
        id=uuid4(),
        name="Test Project",
        admin_id=uuid4(),
        scale_min=scale_min,
        scale_max=scale_max,
        scale_unit=scale_unit,
    )


class TestIsLikertScale:
    """Tests for recognising the standard agreement scale."""

    @pytest.mark.parametrize("unit", ["", "   ", "\t"])
    def test_standard_range_without_a_unit_is_likert(self, unit):
        """
        GIVEN a 0-100 project whose unit is empty or only whitespace
        WHEN the scale is examined
        THEN it counts as the agreement scale

        The unit arrives from a text field, so whitespace is the same as nothing.
        """
        assert is_likert_scale(_project(scale_unit=unit)) is True

    def test_standard_range_with_a_unit_is_not_likert(self):
        """
        GIVEN a 0-100 project measured in percent
        WHEN the scale is examined
        THEN it is not the agreement scale

        A percentage or a budget can share the 0-100 range by coincidence. Naming a unit
        says the number measures that quantity, not agreement.
        """
        assert is_likert_scale(_project(scale_unit="%")) is False

    def test_other_range_is_not_likert(self):
        """
        GIVEN a project on a 1-5 scale
        WHEN the scale is examined
        THEN it is not the agreement scale
        """
        assert is_likert_scale(_project(scale_min=1.0, scale_max=5.0)) is False


class TestDeriveVerdict:
    """Tests for reading a compromise as an agreement verdict."""

    def test_returns_a_verdict_on_the_agreement_scale(self):
        """
        GIVEN a project on the agreement scale and a compromise around 80
        WHEN the verdict is derived
        THEN it names the nearest Likert point and its wording
        """
        # WHEN
        verdict = derive_verdict(_project(), 70.0, 80.0, 90.0)

        # THEN
        assert isinstance(verdict, LikertVerdict)
        assert verdict.value == 75
        assert verdict.decision

    def test_follows_the_compromise_rather_than_the_project(self):
        """
        GIVEN the same project and two different compromises
        WHEN each is read
        THEN the verdicts differ

        This is the property that made storing the verdict a defect: it depends on
        numbers that change, so a copy of it goes stale the moment they do.
        """
        # WHEN
        low = derive_verdict(_project(), 0.0, 5.0, 10.0)
        high = derive_verdict(_project(), 90.0, 95.0, 100.0)

        # THEN
        assert low is not None
        assert high is not None
        assert low.value < high.value

    @pytest.mark.parametrize(
        ("scale_min", "scale_max", "scale_unit"),
        [(0.0, 100.0, "%"), (1.0, 5.0, ""), (0.0, 100.0, "bn CZK")],
    )
    def test_returns_nothing_off_the_agreement_scale(self, scale_min, scale_max, scale_unit):
        """
        GIVEN a project that does not measure agreement
        WHEN the verdict is derived
        THEN there is none, rather than a sentence about agreement
        """
        project = _project(scale_min=scale_min, scale_max=scale_max, scale_unit=scale_unit)

        assert derive_verdict(project, 70.0, 80.0, 90.0) is None

    def test_follows_a_scale_edit_immediately(self):
        """
        GIVEN a project on the agreement scale with a verdict
        WHEN its unit is set, making it a measurement rather than an opinion
        THEN the next read returns no verdict, with nothing to invalidate

        This is the whole point of deriving it. The same edit used to leave a stored
        verdict in place, and a migration had to clean those rows once already.
        """
        # GIVEN
        project = _project()
        assert derive_verdict(project, 70.0, 80.0, 90.0) is not None

        # WHEN
        project.scale_unit = "%"

        # THEN
        assert derive_verdict(project, 70.0, 80.0, 90.0) is None
