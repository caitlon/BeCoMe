"""The example project's numbers must stay equal to the published Floods case.

The seeded project is the first thing a new user sees, and its result is computed by
the real calculator, so a typo in one triple would show a wrong compromise under a
case study the site also publishes. tests/reference/floods_case.py is the source of
truth for those numbers; this module pins the seed data against it.
"""

from api.data.example_project import (
    EXAMPLE_EXPERTS,
    EXAMPLE_PROJECT_TEXT,
    EXAMPLE_SCALE_MAX,
    EXAMPLE_SCALE_MIN,
)
from tests.reference.floods_case import FLOODS_CASE


class TestExampleExpertData:
    """The 13 seeded opinions against the reference case."""

    def test_triples_match_the_reference_case(self):
        """Each expert's triple matches the reference case at the same position.

        The seeded panel must stay in the same order as the published Floods case.
        Reordering EXAMPLE_EXPERTS will fail this test — that is intentional, so
        reordering becomes an explicit decision someone makes on purpose.
        """
        # GIVEN
        reference = [
            (o.opinion.lower_bound, o.opinion.peak, o.opinion.upper_bound)
            for o in FLOODS_CASE["opinions"]
        ]

        # WHEN
        seeded = [(e.lower_bound, e.peak, e.upper_bound) for e in EXAMPLE_EXPERTS]

        # THEN
        assert seeded == reference

    def test_expert_count_matches_the_reference_case(self):
        """The pool holds exactly as many experts as the case has opinions."""
        # GIVEN / WHEN
        count = len(EXAMPLE_EXPERTS)

        # THEN
        assert count == FLOODS_CASE["expected_result"]["num_experts"]

    def test_fuzzy_order_holds_for_every_expert(self):
        """lower <= peak <= upper, which the database also enforces."""
        # GIVEN / WHEN / THEN
        for expert in EXAMPLE_EXPERTS:
            assert expert.lower_bound <= expert.peak <= expert.upper_bound

    def test_values_sit_inside_the_project_scale(self):
        """No opinion falls outside the scale the seeded project declares."""
        # GIVEN / WHEN / THEN
        for expert in EXAMPLE_EXPERTS:
            assert expert.lower_bound >= EXAMPLE_SCALE_MIN
            assert expert.upper_bound <= EXAMPLE_SCALE_MAX

    def test_identities_are_unique(self):
        """Duplicate ids or addresses would break the unique constraints on insert."""
        # GIVEN / WHEN
        ids = {e.user_id for e in EXAMPLE_EXPERTS}
        emails = {e.email for e in EXAMPLE_EXPERTS}

        # THEN
        assert len(ids) == len(EXAMPLE_EXPERTS)
        assert len(emails) == len(EXAMPLE_EXPERTS)

    def test_addresses_are_undeliverable(self):
        """RFC 2606 reserves .invalid, so no mail can ever reach these accounts."""
        # GIVEN / WHEN / THEN
        for expert in EXAMPLE_EXPERTS:
            assert expert.email.endswith("@example.invalid")


class TestExampleProjectText:
    """Both locales are present and distinct."""

    def test_both_locales_present(self):
        """A missing locale would silently fall back to English text."""
        # GIVEN / WHEN / THEN
        assert set(EXAMPLE_PROJECT_TEXT) == {"en", "cs"}

    def test_positions_differ_between_locales(self):
        """A Czech position equal to the English one means a forgotten translation."""
        # GIVEN / WHEN
        untranslated = [e.position_en for e in EXAMPLE_EXPERTS if e.position_cs == e.position_en]

        # THEN
        assert untranslated == []

    def test_position_selects_by_language(self):
        """position() returns Czech for cs and English for anything else."""
        # GIVEN
        expert = EXAMPLE_EXPERTS[0]

        # WHEN / THEN
        assert expert.position("cs") == expert.position_cs
        assert expert.position("en") == expert.position_en
        assert expert.position("de") == expert.position_en
