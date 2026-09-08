"""Tests for the agreement level derived from Δmax and the project's scale."""

import pytest

from api.db.models import Project
from api.services.agreement_level import AgreementLevel, derive_agreement


def _project(scale_min: float = 0.0, scale_max: float = 100.0) -> Project:
    """Build a project carrying only the scale the reading depends on."""
    return Project(name="P", scale_min=scale_min, scale_max=scale_max, scale_unit="%")


class TestDeriveAgreement:
    """The reading of Δmax against the width of the scale."""

    @pytest.mark.parametrize(
        ("max_error", "expected"),
        [
            (0.0, AgreementLevel.HIGH),
            (20.0, AgreementLevel.HIGH),
            (20.001, AgreementLevel.MODERATE),
            (40.0, AgreementLevel.MODERATE),
            (40.001, AgreementLevel.LOW),
            (100.0, AgreementLevel.LOW),
        ],
    )
    def test_thresholds_on_a_zero_to_hundred_scale(
        self, max_error: float, expected: AgreementLevel
    ):
        """Both thresholds are inclusive, as the interface has always read them."""
        # GIVEN a project measured from 0 to 100
        project = _project()

        # WHEN the compromise carries this much error
        level = derive_agreement(project, max_error)

        # THEN it reads as the expected level
        assert level is expected

    def test_the_reading_is_relative_to_the_scale_not_the_number(self):
        """The same Δmax means different things on different scales.

        This is the whole point of dividing by the range: 6 is 6 percent of a 0-100
        scale and 0.06 percent of a 0-10000 one, and those are not the same finding.
        """
        # GIVEN two projects whose scales differ by two orders of magnitude
        narrow = _project(scale_max=10.0)
        wide = _project(scale_max=10000.0)

        # WHEN the same absolute error is read against each
        # THEN the narrow scale calls it low agreement and the wide one high
        assert derive_agreement(narrow, 6.0) is AgreementLevel.LOW
        assert derive_agreement(wide, 6.0) is AgreementLevel.HIGH

    def test_a_negative_lower_bound_uses_the_full_width(self):
        """A scale can start below zero; the width is max minus min, not max."""
        # GIVEN a scale from -50 to 50, so 100 wide
        project = _project(scale_min=-50.0, scale_max=50.0)

        # WHEN the error is a fifth of that width
        # THEN it reads as high, exactly as it would from 0 to 100
        assert derive_agreement(project, 20.0) is AgreementLevel.HIGH
