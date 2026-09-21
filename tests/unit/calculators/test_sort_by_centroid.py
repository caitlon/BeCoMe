"""Unit tests for BeCoMeCalculator.sort_by_centroid."""

import pytest

from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def three_experts_for_sorting():
    """Provide unsorted opinions for testing centroid sorting.

    :return: List of 3 ExpertOpinion instances in unsorted order
    """
    return [
        ExpertOpinion(
            expert_id="E3",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
        ),
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        ),
    ]


@pytest.fixture
def two_experts_for_immutability_test():
    """Provide opinions for testing sort immutability.

    :return: List of 2 ExpertOpinion instances in unsorted order
    """
    return [
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0),
        ),
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=1.0, peak=2.0, upper_bound=3.0),
        ),
    ]


class TestSortByCentroid:
    """Test cases for BeCoMeCalculator.sort_by_centroid."""

    def test_sorts_opinions_in_ascending_centroid_order(
        self, calculator, three_experts_for_sorting
    ):
        """
        GIVEN three opinions in unsorted order
        WHEN sort_by_centroid is called
        THEN they come back in ascending centroid order
        """
        # WHEN
        sorted_opinions = calculator.sort_by_centroid(three_experts_for_sorting)

        # THEN
        assert [op.expert_id for op in sorted_opinions] == ["E1", "E2", "E3"]
        centroids = [op.centroid for op in sorted_opinions]
        assert centroids == sorted(centroids)

    def test_returns_a_new_list_and_leaves_the_input_unchanged(
        self, calculator, two_experts_for_immutability_test
    ):
        """
        GIVEN two opinions in unsorted order
        WHEN sort_by_centroid is called
        THEN a sorted new list comes back and the input keeps its order
        """
        # GIVEN
        original_ids = [op.expert_id for op in two_experts_for_immutability_test]

        # WHEN
        sorted_opinions = calculator.sort_by_centroid(two_experts_for_immutability_test)

        # THEN
        assert [op.expert_id for op in two_experts_for_immutability_test] == original_ids
        assert [op.expert_id for op in sorted_opinions] == ["E1", "E2"]
