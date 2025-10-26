"""
Unit tests for BaseAggregationCalculator ABC contract validation.

This module tests that:
1. BaseAggregationCalculator is a proper abstract base class
2. BeCoMeCalculator correctly implements the ABC interface
3. Abstract methods cannot be instantiated directly
"""

import pytest

from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestBaseAggregationCalculatorABC:
    """Test cases for BaseAggregationCalculator abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        """Test that BaseAggregationCalculator cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseAggregationCalculator()  # type: ignore

        assert "abstract" in str(exc_info.value).lower()
        assert "BaseAggregationCalculator" in str(exc_info.value)

    def test_abstract_methods_are_defined(self):
        """Test that all required abstract methods are defined in ABC."""
        abstract_methods = BaseAggregationCalculator.__abstractmethods__

        assert "calculate_arithmetic_mean" in abstract_methods
        assert "calculate_median" in abstract_methods
        assert "calculate_compromise" in abstract_methods
        assert len(abstract_methods) == 3

    def test_become_calculator_inherits_from_abc(self):
        """Test that BeCoMeCalculator properly inherits from BaseAggregationCalculator."""
        assert issubclass(BeCoMeCalculator, BaseAggregationCalculator)

    def test_become_calculator_implements_all_abstract_methods(self):
        """Test that BeCoMeCalculator implements all required abstract methods."""
        calculator = BeCoMeCalculator()

        # Check that all abstract methods are implemented
        assert hasattr(calculator, "calculate_arithmetic_mean")
        assert hasattr(calculator, "calculate_median")
        assert hasattr(calculator, "calculate_compromise")

        # Check that they are callable
        assert callable(calculator.calculate_arithmetic_mean)
        assert callable(calculator.calculate_median)
        assert callable(calculator.calculate_compromise)

    def test_become_calculator_can_be_used_polymorphically(self):
        """Test that BeCoMeCalculator can be used where BaseAggregationCalculator is expected."""
        calculator: BaseAggregationCalculator = BeCoMeCalculator()

        # Create test data
        opinions = [
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(5.0, 10.0, 15.0)),
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(7.0, 12.0, 17.0)),
        ]

        # Test that polymorphic call works
        mean = calculator.calculate_arithmetic_mean(opinions)
        assert isinstance(mean, FuzzyTriangleNumber)

        median = calculator.calculate_median(opinions)
        assert isinstance(median, FuzzyTriangleNumber)

        result = calculator.calculate_compromise(opinions)
        assert result.num_experts == 2

    def test_abc_method_signatures_match_implementation(self):
        """Test that BeCoMeCalculator method signatures match ABC interface."""
        from inspect import signature

        # Get method signatures from ABC
        abc_mean_sig = signature(BaseAggregationCalculator.calculate_arithmetic_mean)
        abc_median_sig = signature(BaseAggregationCalculator.calculate_median)
        abc_compromise_sig = signature(BaseAggregationCalculator.calculate_compromise)

        # Get method signatures from implementation
        impl_mean_sig = signature(BeCoMeCalculator.calculate_arithmetic_mean)
        impl_median_sig = signature(BeCoMeCalculator.calculate_median)
        impl_compromise_sig = signature(BeCoMeCalculator.calculate_compromise)

        # Check that signatures match (parameters and return types)
        assert str(abc_mean_sig) == str(impl_mean_sig)
        assert str(abc_median_sig) == str(impl_median_sig)
        assert str(abc_compromise_sig) == str(impl_compromise_sig)


class TestBeCoMeCalculatorPublicInterface:
    """Test cases for BeCoMeCalculator public methods."""

    def test_sort_by_centroid_is_public(self):
        """Test that sort_by_centroid is a public method (no leading underscore)."""
        calculator = BeCoMeCalculator()

        # Check that the method exists and is public
        assert hasattr(calculator, "sort_by_centroid")
        assert not hasattr(calculator, "_sort_by_centroid")  # Old private name should not exist

        # Check that it's callable
        assert callable(calculator.sort_by_centroid)

    def test_sort_by_centroid_works_correctly(self):
        """Test that sort_by_centroid correctly sorts opinions by centroid."""
        calculator = BeCoMeCalculator()

        opinions = [
            ExpertOpinion(
                expert_id="E3", opinion=FuzzyTriangleNumber(10.0, 15.0, 20.0)
            ),  # centroid: 15.0
            ExpertOpinion(
                expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)
            ),  # centroid: 2.0
            ExpertOpinion(
                expert_id="E2", opinion=FuzzyTriangleNumber(5.0, 10.0, 15.0)
            ),  # centroid: 10.0
        ]

        sorted_opinions = calculator.sort_by_centroid(opinions)

        # Check that opinions are sorted by centroid
        assert sorted_opinions[0].expert_id == "E1"  # centroid: 2.0
        assert sorted_opinions[1].expert_id == "E2"  # centroid: 10.0
        assert sorted_opinions[2].expert_id == "E3"  # centroid: 15.0

        # Check that centroids are in ascending order
        centroids = [op.centroid for op in sorted_opinions]
        assert centroids == sorted(centroids)

    def test_sort_by_centroid_preserves_original_list(self):
        """Test that sort_by_centroid returns new list without modifying original."""
        calculator = BeCoMeCalculator()

        original_opinions = [
            ExpertOpinion(expert_id="E2", opinion=FuzzyTriangleNumber(10.0, 15.0, 20.0)),
            ExpertOpinion(expert_id="E1", opinion=FuzzyTriangleNumber(1.0, 2.0, 3.0)),
        ]

        # Get original order
        original_ids = [op.expert_id for op in original_opinions]

        # Sort
        sorted_opinions = calculator.sort_by_centroid(original_opinions)

        # Check that original list is unchanged
        current_ids = [op.expert_id for op in original_opinions]
        assert current_ids == original_ids

        # Check that sorted list is different
        sorted_ids = [op.expert_id for op in sorted_opinions]
        assert sorted_ids != original_ids
