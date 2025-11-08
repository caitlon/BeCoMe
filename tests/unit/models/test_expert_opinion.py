"""
Unit tests for ExpertOpinion class.
"""

import pytest

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def expert_opinion_e1(standard_fuzzy):
    """Fixture providing an ExpertOpinion with ID 'E1'.

    Uses standard_fuzzy fixture from conftest.py.
    This fixture implements the GIVEN step by preparing test data
    that can be injected into any test via Dependency Injection.
    """
    return ExpertOpinion(expert_id="E1", opinion=standard_fuzzy)


@pytest.fixture
def expert_opinion_e2():
    """Fixture providing an ExpertOpinion with ID 'E2' and different values.

    This expert has higher values than E1, useful for comparison tests.
    """
    fuzzy = FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0)
    return ExpertOpinion(expert_id="E2", opinion=fuzzy)


class TestExpertOpinionCreation:
    """Test cases for ExpertOpinion object creation."""

    def test_valid_creation(self, expert_opinion_e1, standard_fuzzy):
        """Test creating a valid expert opinion."""
        # GIVEN - Expert opinion from fixture

        # WHEN - Already created by fixture

        # THEN - Verify all attributes are set correctly
        assert expert_opinion_e1.expert_id == "E1", (
            f"Expected expert_id to be 'E1', got '{expert_opinion_e1.expert_id}'"
        )
        assert expert_opinion_e1.opinion == standard_fuzzy, (
            "Expected opinion to match standard_fuzzy"
        )
        assert expert_opinion_e1.opinion.lower_bound == 5.0, (
            f"Expected lower_bound to be 5.0, got {expert_opinion_e1.opinion.lower_bound}"
        )
        assert expert_opinion_e1.opinion.peak == 10.0, (
            f"Expected peak to be 10.0, got {expert_opinion_e1.opinion.peak}"
        )
        assert expert_opinion_e1.opinion.upper_bound == 15.0, (
            f"Expected upper_bound to be 15.0, got {expert_opinion_e1.opinion.upper_bound}"
        )

    def test_creation_with_numeric_id(self):
        """Test creating expert opinion with numeric ID as string."""
        # GIVEN - Fuzzy number and numeric string ID
        fuzzy = FuzzyTriangleNumber(lower_bound=3.0, peak=7.0, upper_bound=11.0)
        expert_id = "001"

        # WHEN - Create expert opinion
        opinion = ExpertOpinion(expert_id=expert_id, opinion=fuzzy)

        # THEN - Verify attributes are set correctly
        assert opinion.expert_id == "001", (
            f"Expected expert_id to be '001', got '{opinion.expert_id}'"
        )
        assert opinion.opinion == fuzzy, "Expected opinion to match provided fuzzy number"


# NOTE: Centroid tests were removed as they are redundant.
# ExpertOpinion.centroid simply delegates to FuzzyTriangleNumber.centroid,
# which is thoroughly tested in test_fuzzy_number.py.
# Testing simple delegation doesn't add value.


class TestExpertOpinionComparison:
    """Test cases for comparison operators."""

    def test_less_than_comparison(self):
        """Test __lt__ operator based on centroids."""
        # GIVEN - Two expert opinions with different centroids
        opinion1 = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        )  # centroid = 6.0
        opinion2 = ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        )  # centroid = 12.0

        # WHEN/THEN - Compare using < operator
        assert opinion1 < opinion2, "Expected opinion1 (centroid=6.0) < opinion2 (centroid=12.0)"
        assert not opinion2 < opinion1, "Expected not (opinion2 < opinion1)"

    def test_less_than_or_equal_comparison(self):
        """Test __le__ operator."""
        # GIVEN - Three expert opinions (two equal, one greater)
        opinion1 = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        )
        opinion3 = ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        )

        # WHEN/THEN - Test <= operator with equal and less than cases
        assert opinion1 <= opinion2, "Expected opinion1 <= opinion2 (equal centroids)"
        assert opinion1 <= opinion3, "Expected opinion1 <= opinion3 (less than)"
        assert not opinion3 <= opinion1, "Expected not (opinion3 <= opinion1)"

    def test_equality_comparison(self, standard_fuzzy):
        """Test __eq__ operator."""
        # GIVEN - Three expert opinions (two identical, one different ID)
        opinion1 = ExpertOpinion(expert_id="Expert 1", opinion=standard_fuzzy)
        opinion2 = ExpertOpinion(expert_id="Expert 1", opinion=standard_fuzzy)
        opinion3 = ExpertOpinion(expert_id="Expert 2", opinion=standard_fuzzy)

        # WHEN/THEN - Test equality
        assert opinion1 == opinion2, "Expected opinions with same ID and fuzzy number to be equal"
        assert opinion1 != opinion3, "Expected opinions with different IDs to not be equal"

    def test_equality_with_different_opinion(self):
        """Test equality with different fuzzy numbers."""
        # GIVEN - Two opinions with same ID but different fuzzy numbers
        opinion1 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=10.0, upper_bound=15.0),
        )

        # WHEN/THEN - They should not be equal
        assert opinion1 != opinion2, (
            "Expected opinions with different fuzzy numbers to not be equal"
        )

    def test_equality_with_non_expert_opinion(self, expert_opinion_e1):
        """Test equality comparison with non-ExpertOpinion object."""
        # GIVEN - Expert opinion and various non-ExpertOpinion objects

        # WHEN/THEN - Compare with different types
        assert expert_opinion_e1 != "not an expert opinion", (
            "Expected expert opinion to not equal string"
        )
        assert expert_opinion_e1 != 42, "Expected expert opinion to not equal int"
        assert expert_opinion_e1 is not None, "Expected expert opinion to not be None"


class TestExpertOpinionSorting:
    """Test cases for sorting expert opinions."""

    def test_sorting_three_opinions(self):
        """Test sorting a list of expert opinions by centroid."""
        # GIVEN - List of three opinions in unsorted order
        opinions = [
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),  # centroid = 12.0
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),  # centroid = 6.0
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),  # centroid = 9.0
        ]

        # WHEN - Sort the list
        sorted_opinions = sorted(opinions)

        # THEN - Verify sorted order by centroid (ascending)
        assert sorted_opinions[0].expert_id == "E1", "Expected E1 first (centroid=6.0)"
        assert sorted_opinions[1].expert_id == "E2", "Expected E2 second (centroid=9.0)"
        assert sorted_opinions[2].expert_id == "E3", "Expected E3 third (centroid=12.0)"

    def test_sorting_excel_example(self):
        """Test sorting with data similar to Excel example."""
        # GIVEN - List with three opinions from Excel example
        opinions = [
            ExpertOpinion(
                expert_id="Project manager",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=15.0),
            ),  # centroid = 13.33
            ExpertOpinion(
                expert_id="Product owner",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=11.0, upper_bound=14.0),
            ),  # centroid = 11.0
            ExpertOpinion(
                expert_id="Software architect",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=10.0, upper_bound=13.0),
            ),  # centroid = 10.0
        ]

        # WHEN - Sort the list
        sorted_opinions = sorted(opinions)

        # THEN - Verify sorted order matches expected centroids
        assert sorted_opinions[0].expert_id == "Software architect", (
            "Expected Software architect first (centroid=10.0)"
        )
        assert sorted_opinions[1].expert_id == "Product owner", (
            "Expected Product owner second (centroid=11.0)"
        )
        assert sorted_opinions[2].expert_id == "Project manager", (
            "Expected Project manager third (centroid=13.33)"
        )


class TestExpertOpinionStringRepresentation:
    """Test cases for string representation."""

    def test_repr_representation(self, expert_opinion_e1):
        """Test __repr__ method."""
        # GIVEN - Expert opinion from fixture

        # WHEN - Get repr representation
        repr_str = repr(expert_opinion_e1)

        # THEN - Verify repr contains necessary information
        assert "ExpertOpinion" in repr_str, f"Expected 'ExpertOpinion' in repr, got: {repr_str}"
        assert "E1" in repr_str, f"Expected 'E1' in repr, got: {repr_str}"
        assert "opinion=" in repr_str, f"Expected 'opinion=' in repr, got: {repr_str}"

    def test_repr_contains_all_info(self):
        """Test that repr contains complete information."""
        # GIVEN - Expert opinion with specific fuzzy values
        fuzzy = FuzzyTriangleNumber(lower_bound=7.0, peak=14.0, upper_bound=21.0)
        opinion = ExpertOpinion(expert_id="Test Expert", opinion=fuzzy)

        # WHEN - Get repr representation
        repr_str = repr(opinion)

        # THEN - Verify all information is present
        assert "Test Expert" in repr_str, f"Expected 'Test Expert' in repr, got: {repr_str}"
        assert "7.0" in repr_str, f"Expected '7.0' in repr, got: {repr_str}"
        assert "14.0" in repr_str, f"Expected '14.0' in repr, got: {repr_str}"
        assert "21.0" in repr_str, f"Expected '21.0' in repr, got: {repr_str}"

    def test_str_representation(self, expert_opinion_e1):
        """Test __str__ method for human-readable output."""
        # GIVEN - Expert opinion from fixture

        # WHEN - Convert to string
        str_repr = str(expert_opinion_e1)

        # THEN - Verify formatted string
        assert str_repr == "E1: (5.00, 10.00, 15.00)", (
            f"Expected 'E1: (5.00, 10.00, 15.00)', got '{str_repr}'"
        )


class TestExpertOpinionImmutability:
    """Test cases for immutability (frozen dataclass)."""

    @pytest.mark.parametrize(
        "attribute_name,new_value",
        [
            ("expert_id", "E2"),
            ("opinion", FuzzyTriangleNumber(lower_bound=10.0, peak=20.0, upper_bound=30.0)),
        ],
        ids=["frozen_expert_id", "frozen_opinion"],
    )
    def test_frozen_attributes(self, expert_opinion_e1, attribute_name, new_value):
        """Test that all attributes cannot be modified after creation.

        This parametrized test verifies immutability of ExpertOpinion attributes,
        following DRY principle from Lott's book.
        """
        # GIVEN - Expert opinion from fixture

        # WHEN/THEN - Attempt to modify attribute should raise error
        with pytest.raises((AttributeError, TypeError)) as exc_info:
            setattr(expert_opinion_e1, attribute_name, new_value)

        assert exc_info.value is not None, f"Expected error when modifying {attribute_name}"

    def test_delattr_raises_error(self, expert_opinion_e1):
        """Test that deleting attributes is prevented."""
        # GIVEN - Expert opinion from fixture

        # WHEN/THEN - Attempt to delete attribute should raise AttributeError
        with pytest.raises(AttributeError) as exc_info:
            del expert_opinion_e1.expert_id

        assert "Cannot delete immutable ExpertOpinion attribute" in str(exc_info.value), (
            f"Expected specific error message, got: {exc_info.value}"
        )

    def test_immutable_value_object(self, standard_fuzzy):
        """Test that ExpertOpinion behaves as immutable value object."""
        # GIVEN - Two expert opinions with identical values
        opinion1 = ExpertOpinion(expert_id="E1", opinion=standard_fuzzy)
        opinion2 = ExpertOpinion(expert_id="E1", opinion=standard_fuzzy)

        # WHEN - Compare them

        # THEN - Same values should create equal objects
        assert opinion1 == opinion2, "Expected opinions with same values to be equal"
        # THEN - But they are different instances
        assert opinion1 is not opinion2, "Expected different object instances"

    def test_hashable_for_use_in_sets(self):
        """Test that frozen ExpertOpinion is hashable."""
        # GIVEN - Three expert opinions (two identical, one different)
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0)

        opinion1 = ExpertOpinion(expert_id="E1", opinion=fuzzy1)
        opinion2 = ExpertOpinion(expert_id="E1", opinion=fuzzy1)
        opinion3 = ExpertOpinion(expert_id="E2", opinion=fuzzy2)

        # WHEN - Create a set
        opinion_set = {opinion1, opinion2, opinion3}

        # THEN - Set should contain only 2 elements (opinion1==opinion2)
        assert len(opinion_set) == 2, f"Expected set to have 2 elements, got {len(opinion_set)}"
