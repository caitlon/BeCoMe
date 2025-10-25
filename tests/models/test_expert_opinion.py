"""
Unit tests for ExpertOpinion class.
"""

import pytest

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestExpertOpinionCreation:
    """Test cases for ExpertOpinion object creation."""

    def test_valid_creation(self):
        """Test creating a valid expert opinion."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        opinion = ExpertOpinion(expert_id="Expert 1", opinion=fuzzy)

        assert opinion.expert_id == "Expert 1"
        assert opinion.opinion == fuzzy
        assert opinion.opinion.lower_bound == 5.0
        assert opinion.opinion.peak == 10.0
        assert opinion.opinion.upper_bound == 15.0

    def test_creation_with_numeric_id(self):
        """Test creating expert opinion with numeric ID as string."""
        fuzzy = FuzzyTriangleNumber(lower_bound=3.0, peak=7.0, upper_bound=11.0)
        opinion = ExpertOpinion(expert_id="001", opinion=fuzzy)

        assert opinion.expert_id == "001"
        assert opinion.opinion == fuzzy


class TestExpertOpinionCentroid:
    """Test cases for centroid delegation."""

    def test_get_centroid(self):
        """Test that get_centroid delegates to fuzzy number."""
        fuzzy = FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0)
        opinion = ExpertOpinion(expert_id="Expert A", opinion=fuzzy)

        expected_centroid = (6.0 + 9.0 + 12.0) / 3.0
        assert opinion.get_centroid() == expected_centroid
        assert opinion.get_centroid() == fuzzy.get_centroid()

    def test_centroid_from_excel_example(self):
        """Test centroid with Excel data example."""
        # Product owner from Excel: best=11, lower=8, upper=14
        fuzzy = FuzzyTriangleNumber(lower_bound=8.0, peak=11.0, upper_bound=14.0)
        opinion = ExpertOpinion(expert_id="Product owner", opinion=fuzzy)

        expected_centroid = (8.0 + 11.0 + 14.0) / 3.0
        assert abs(opinion.get_centroid() - expected_centroid) < 1e-10
        assert abs(opinion.get_centroid() - 11.0) < 1e-10


class TestExpertOpinionComparison:
    """Test cases for comparison operators."""

    def test_less_than_comparison(self):
        """Test __lt__ operator based on centroids."""
        opinion1 = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
        )

        # opinion1 centroid = 6.0, opinion2 centroid = 12.0
        assert opinion1 < opinion2
        assert not opinion2 < opinion1

    def test_less_than_or_equal_comparison(self):
        """Test __le__ operator."""
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

        assert opinion1 <= opinion2  # Equal centroids
        assert opinion1 <= opinion3  # Less than
        assert not opinion3 <= opinion1

    def test_equality_comparison(self):
        """Test __eq__ operator."""
        opinion1 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )
        opinion3 = ExpertOpinion(
            expert_id="Expert 2",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        assert opinion1 == opinion2
        assert opinion1 != opinion3  # Different expert_id

    def test_equality_with_different_opinion(self):
        """Test equality with different fuzzy numbers."""
        opinion1 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )
        opinion2 = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=10.0, upper_bound=15.0),
        )

        assert opinion1 != opinion2

    def test_equality_with_non_expert_opinion(self):
        """Test equality comparison with non-ExpertOpinion object."""
        opinion = ExpertOpinion(
            expert_id="Expert 1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        assert opinion != "not an expert opinion"
        assert opinion != 42
        assert opinion is not None


class TestExpertOpinionSorting:
    """Test cases for sorting expert opinions."""

    def test_sorting_three_opinions(self):
        """Test sorting a list of expert opinions by centroid."""
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

        sorted_opinions = sorted(opinions)

        assert sorted_opinions[0].expert_id == "E1"  # centroid = 6.0
        assert sorted_opinions[1].expert_id == "E2"  # centroid = 9.0
        assert sorted_opinions[2].expert_id == "E3"  # centroid = 12.0

    def test_sorting_excel_example(self):
        """Test sorting with data similar to Excel example."""
        # Simplified from Excel: Project manager, Product owner, Software architect
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

        sorted_opinions = sorted(opinions)

        # Software architect has lowest centroid (10.0)
        # Product owner has middle centroid (11.0)
        # Project manager has highest centroid (13.33)
        assert sorted_opinions[0].expert_id == "Software architect"
        assert sorted_opinions[1].expert_id == "Product owner"
        assert sorted_opinions[2].expert_id == "Project manager"


class TestExpertOpinionStringRepresentation:
    """Test cases for string representation."""

    def test_repr_representation(self):
        """Test __repr__ method."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        opinion = ExpertOpinion(expert_id="Expert 1", opinion=fuzzy)

        repr_str = repr(opinion)
        assert "ExpertOpinion" in repr_str
        assert "Expert 1" in repr_str
        assert "opinion=" in repr_str

    def test_repr_contains_all_info(self):
        """Test that repr contains complete information."""
        fuzzy = FuzzyTriangleNumber(lower_bound=7.0, peak=14.0, upper_bound=21.0)
        opinion = ExpertOpinion(expert_id="Test Expert", opinion=fuzzy)

        repr_str = repr(opinion)
        assert "Test Expert" in repr_str
        assert "7.0" in repr_str
        assert "14.0" in repr_str
        assert "21.0" in repr_str


class TestExpertOpinionImmutability:
    """Test cases for immutability (frozen dataclass)."""

    def test_frozen_expert_id(self):
        """Test that expert_id cannot be modified after creation."""
        opinion = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        with pytest.raises((AttributeError, TypeError)):
            opinion.expert_id = "E2"

    def test_frozen_opinion(self):
        """Test that opinion cannot be replaced after creation."""
        opinion = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        new_fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=20.0, upper_bound=30.0)
        with pytest.raises((AttributeError, TypeError)):
            opinion.opinion = new_fuzzy

    def test_immutable_value_object(self):
        """Test that ExpertOpinion behaves as immutable value object."""
        fuzzy = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        opinion1 = ExpertOpinion(expert_id="E1", opinion=fuzzy)
        opinion2 = ExpertOpinion(expert_id="E1", opinion=fuzzy)

        # Same values should create equal objects
        assert opinion1 == opinion2
        # But they are different instances
        assert opinion1 is not opinion2

    def test_hashable_for_use_in_sets(self):
        """Test that frozen ExpertOpinion is hashable."""
        fuzzy1 = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        fuzzy2 = FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0)

        opinion1 = ExpertOpinion(expert_id="E1", opinion=fuzzy1)
        opinion2 = ExpertOpinion(expert_id="E1", opinion=fuzzy1)
        opinion3 = ExpertOpinion(expert_id="E2", opinion=fuzzy2)

        # Can be used in sets
        opinion_set = {opinion1, opinion2, opinion3}
        assert len(opinion_set) == 2  # opinion1 and opinion2 are equal
