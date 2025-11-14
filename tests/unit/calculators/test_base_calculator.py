"""Unit tests for BaseAggregationCalculator abstract base class contract."""

import pytest

from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def two_experts_for_polymorphism():
    """Provide opinions for testing polymorphic ABC implementation.

    :return: List of 2 ExpertOpinion instances
    """
    return [
        ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        ),
        ExpertOpinion(
            expert_id="E2",
            opinion=FuzzyTriangleNumber(lower_bound=7.0, peak=12.0, upper_bound=17.0),
        ),
    ]


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


class TestBaseAggregationCalculatorABC:
    """Test cases for BaseAggregationCalculator abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that BaseAggregationCalculator cannot be instantiated directly."""
        # WHEN / THEN
        with pytest.raises(TypeError) as exc_info:
            BaseAggregationCalculator()  # type: ignore

        assert "abstract" in str(exc_info.value).lower()
        assert "BaseAggregationCalculator" in str(exc_info.value)

    def test_abstract_methods_are_defined(self):
        """Test that all required abstract methods are defined in ABC."""
        # WHEN
        abstract_methods = BaseAggregationCalculator.__abstractmethods__

        # THEN
        assert "calculate_arithmetic_mean" in abstract_methods
        assert "calculate_median" in abstract_methods
        assert "calculate_compromise" in abstract_methods
        assert "sort_by_centroid" in abstract_methods
        assert len(abstract_methods) == 4

    def test_become_calculator_implements_abc_interface(
        self, calculator, two_experts_for_polymorphism
    ):
        """Test that BeCoMeCalculator properly implements ABC interface."""
        # GIVEN
        assert issubclass(BeCoMeCalculator, BaseAggregationCalculator)
        polymorphic_calculator: BaseAggregationCalculator = calculator

        # WHEN
        mean = polymorphic_calculator.calculate_arithmetic_mean(two_experts_for_polymorphism)
        median = polymorphic_calculator.calculate_median(two_experts_for_polymorphism)
        result = polymorphic_calculator.calculate_compromise(two_experts_for_polymorphism)

        # THEN
        assert isinstance(mean, FuzzyTriangleNumber)
        assert isinstance(median, FuzzyTriangleNumber)
        assert result.num_experts == 2


class TestAbstractMethodEnforcement:
    """Test that abstract methods properly enforce implementation."""

    def test_incomplete_implementation_raises_error(self):
        """Test that partial ABC implementation raises TypeError."""

        # GIVEN
        class IncompleteCalculator(BaseAggregationCalculator):
            def calculate_arithmetic_mean(self, opinions):
                return opinions[0].opinion

        # WHEN / THEN
        with pytest.raises(TypeError) as exc_info:
            IncompleteCalculator()  # type: ignore

        assert "abstract" in str(exc_info.value).lower()


class TestBeCoMeCalculatorPublicInterface:
    """Test cases for BeCoMeCalculator public methods."""

    def test_sort_by_centroid_works_correctly(self, calculator, three_experts_for_sorting):
        """Test that sort_by_centroid sorts opinions in ascending order by centroid."""
        # WHEN
        sorted_opinions = calculator.sort_by_centroid(three_experts_for_sorting)

        # THEN
        assert sorted_opinions[0].expert_id == "E1"
        assert sorted_opinions[1].expert_id == "E2"
        assert sorted_opinions[2].expert_id == "E3"

        centroids = [op.centroid for op in sorted_opinions]
        assert centroids == sorted(centroids)

    def test_sort_by_centroid_preserves_original_list(
        self, calculator, two_experts_for_immutability_test
    ):
        """Test that sort_by_centroid returns new list without modifying original."""
        # GIVEN
        original_ids = [op.expert_id for op in two_experts_for_immutability_test]

        # WHEN
        sorted_opinions = calculator.sort_by_centroid(two_experts_for_immutability_test)

        # THEN
        current_ids = [op.expert_id for op in two_experts_for_immutability_test]
        assert current_ids == original_ids

        sorted_ids = [op.expert_id for op in sorted_opinions]
        assert sorted_ids != original_ids
        assert sorted_ids == ["E1", "E2"]
