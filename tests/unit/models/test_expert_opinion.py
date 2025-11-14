"""Unit tests for ExpertOpinion class."""

import pytest

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def expert_opinion_e1(standard_fuzzy):
    """Fixture providing an ExpertOpinion with ID 'E1'.

    :param standard_fuzzy: FuzzyTriangleNumber fixture
    :return: ExpertOpinion instance with ID 'E1'
    """
    return ExpertOpinion(expert_id="E1", opinion=standard_fuzzy)


@pytest.fixture
def expert_opinion_e2():
    """Fixture providing an ExpertOpinion with ID 'E2'.

    :return: ExpertOpinion instance with ID 'E2' and fuzzy(9.0, 12.0, 15.0)
    """
    fuzzy = FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0)
    return ExpertOpinion(expert_id="E2", opinion=fuzzy)


class TestExpertOpinionCreation:
    """Test cases for ExpertOpinion object creation."""

    def test_valid_creation(self, expert_opinion_e1, standard_fuzzy):
        """Test creating a valid expert opinion."""
        # THEN
        assert expert_opinion_e1.expert_id == "E1"
        assert expert_opinion_e1.opinion == standard_fuzzy
        assert expert_opinion_e1.opinion.lower_bound == 5.0
        assert expert_opinion_e1.opinion.peak == 10.0
        assert expert_opinion_e1.opinion.upper_bound == 15.0

    def test_creation_with_numeric_id(self):
        """Test creating expert opinion with numeric ID as string."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower_bound=3.0, peak=7.0, upper_bound=11.0)
        expert_id = "001"

        # WHEN
        opinion = ExpertOpinion(expert_id=expert_id, opinion=fuzzy)

        # THEN
        assert opinion.expert_id == "001"
        assert opinion.opinion == fuzzy


# NOTE: Centroid tests were removed as they are redundant.
# ExpertOpinion.centroid simply delegates to FuzzyTriangleNumber.centroid,
# which is thoroughly tested in test_fuzzy_number.py.
# Testing simple delegation doesn't add value.


class TestExpertOpinionComparison:
    """Test cases for comparison operators."""

    def test_less_than_comparison(self):
        """Test __lt__ operator based on centroids."""
        # GIVEN
        opinion1 = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        )

        # WHEN / THEN
        assert opinion1 < opinion2
        assert not opinion2 < opinion1

    def test_less_than_or_equal_comparison(self):
        """Test __le__ operator."""
        # GIVEN
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

        # WHEN / THEN
        assert opinion1 <= opinion2
        assert opinion1 <= opinion3
        assert not opinion3 <= opinion1

    def test_equality_comparison(self, standard_fuzzy):
        """Test __eq__ operator."""
        # GIVEN
        opinion1 = ExpertOpinion(expert_id="Expert 1", opinion=standard_fuzzy)
        opinion2 = ExpertOpinion(expert_id="Expert 1", opinion=standard_fuzzy)
        opinion3 = ExpertOpinion(expert_id="Expert 2", opinion=standard_fuzzy)

        # WHEN / THEN
        assert opinion1 == opinion2
        assert opinion1 != opinion3

    def test_equality_with_different_opinion(self):
        """Test equality with different fuzzy numbers."""
        # GIVEN
        opinion1 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=10.0, upper_bound=15.0),
        )

        # WHEN / THEN
        assert opinion1 != opinion2

    def test_equality_with_non_expert_opinion(self, expert_opinion_e1):
        """Test equality comparison with non-ExpertOpinion object."""
        # WHEN / THEN
        assert expert_opinion_e1 != "not an expert opinion"
        assert expert_opinion_e1 != 42
        assert expert_opinion_e1 is not None


class TestExpertOpinionSorting:
    """Test cases for sorting expert opinions."""

    def test_sorting_three_opinions(self):
        """Test sorting a list of expert opinions by centroid."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id="E3",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="E1",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),
            ExpertOpinion(
                expert_id="E2",
                opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
            ),
        ]

        # WHEN
        sorted_opinions = sorted(opinions)

        # THEN
        assert sorted_opinions[0].expert_id == "E1"
        assert sorted_opinions[1].expert_id == "E2"
        assert sorted_opinions[2].expert_id == "E3"

    def test_sorting_excel_example(self):
        """Test sorting with data similar to Excel example."""
        # GIVEN
        opinions = [
            ExpertOpinion(
                expert_id="Project manager",
                opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=15.0),
            ),
            ExpertOpinion(
                expert_id="Product owner",
                opinion=FuzzyTriangleNumber(lower_bound=8.0, peak=11.0, upper_bound=14.0),
            ),
            ExpertOpinion(
                expert_id="Software architect",
                opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=10.0, upper_bound=13.0),
            ),
        ]

        # WHEN
        sorted_opinions = sorted(opinions)

        # THEN
        assert sorted_opinions[0].expert_id == "Software architect"
        assert sorted_opinions[1].expert_id == "Product owner"
        assert sorted_opinions[2].expert_id == "Project manager"


class TestExpertOpinionStringRepresentation:
    """Test cases for string representation."""

    def test_repr_representation(self, expert_opinion_e1):
        """Test __repr__ method."""
        # WHEN
        repr_str = repr(expert_opinion_e1)

        # THEN
        assert "ExpertOpinion" in repr_str
        assert "E1" in repr_str
        assert "opinion=" in repr_str

    def test_repr_contains_all_info(self):
        """Test that repr contains complete information."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower_bound=7.0, peak=14.0, upper_bound=21.0)
        opinion = ExpertOpinion(expert_id="Test Expert", opinion=fuzzy)

        # WHEN
        repr_str = repr(opinion)

        # THEN
        assert "Test Expert" in repr_str
        assert "7.0" in repr_str
        assert "14.0" in repr_str
        assert "21.0" in repr_str

    def test_str_representation(self, expert_opinion_e1):
        """Test __str__ method for human-readable output."""
        # WHEN
        str_repr = str(expert_opinion_e1)

        # THEN
        assert str_repr == "E1: (5.00, 10.00, 15.00)"


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
        """Test that all attributes cannot be modified after creation."""
        # WHEN / THEN
        with pytest.raises((AttributeError, TypeError)) as exc_info:
            setattr(expert_opinion_e1, attribute_name, new_value)

        assert exc_info.value is not None

    def test_delattr_raises_error(self, expert_opinion_e1):
        """Test that deleting attributes is prevented."""
        # WHEN / THEN
        with pytest.raises(AttributeError) as exc_info:
            del expert_opinion_e1.expert_id

        assert "Cannot delete immutable ExpertOpinion attribute" in str(exc_info.value)

    def test_immutable_value_object(self, standard_fuzzy):
        """Test that ExpertOpinion behaves as immutable value object."""
        # GIVEN
        opinion1 = ExpertOpinion(expert_id="E1", opinion=standard_fuzzy)
        opinion2 = ExpertOpinion(expert_id="E1", opinion=standard_fuzzy)

        # THEN
        assert opinion1 == opinion2
        assert opinion1 is not opinion2

    def test_hashable_for_use_in_sets(self):
        """Test that frozen ExpertOpinion is hashable."""
        # GIVEN
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0)

        opinion1 = ExpertOpinion(expert_id="E1", opinion=fuzzy1)
        opinion2 = ExpertOpinion(expert_id="E1", opinion=fuzzy1)
        opinion3 = ExpertOpinion(expert_id="E2", opinion=fuzzy2)

        # WHEN
        opinion_set = {opinion1, opinion2, opinion3}

        # THEN
        assert len(opinion_set) == 2
