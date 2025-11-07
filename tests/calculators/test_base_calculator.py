"""
Unit tests for BaseAggregationCalculator ABC contract validation.

Following Lott's "Python Object-Oriented Programming" (Chapter 13):
- Tests structured as GIVEN-WHEN-THEN
- Fixtures provide test data (Dependency Injection)
- Each test validates a single behavior

This module tests that:
1. BaseAggregationCalculator is a proper abstract base class
2. BeCoMeCalculator correctly implements the ABC interface
3. Abstract methods cannot be instantiated directly
"""

import pytest

from src.calculators.base_calculator import BaseAggregationCalculator
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestBaseAggregationCalculatorABC:
    """Test cases for BaseAggregationCalculator abstract base class."""

    def test_cannot_instantiate_abstract_base_class(self):
        """
        Test that BaseAggregationCalculator cannot be instantiated directly.

        GIVEN: BaseAggregationCalculator ABC
        WHEN: Attempting to instantiate it directly
        THEN: TypeError is raised mentioning "abstract"
        """
        # GIVEN: BaseAggregationCalculator is an ABC

        # WHEN/THEN: Attempting to instantiate raises TypeError
        with pytest.raises(TypeError) as exc_info:
            BaseAggregationCalculator()  # type: ignore

        # THEN: Error message mentions both "abstract" and class name
        assert "abstract" in str(exc_info.value).lower()
        assert "BaseAggregationCalculator" in str(exc_info.value)

    def test_abstract_methods_are_defined(self):
        """
        Test that all required abstract methods are defined in ABC.

        GIVEN: BaseAggregationCalculator ABC
        WHEN: Inspecting its abstract methods
        THEN: All 4 expected abstract methods are present
        """
        # GIVEN: BaseAggregationCalculator ABC exists

        # WHEN: Accessing __abstractmethods__
        abstract_methods = BaseAggregationCalculator.__abstractmethods__

        # THEN: All 4 required abstract methods are defined
        assert "calculate_arithmetic_mean" in abstract_methods
        assert "calculate_median" in abstract_methods
        assert "calculate_compromise" in abstract_methods
        assert "sort_by_centroid" in abstract_methods
        assert len(abstract_methods) == 4

    def test_become_calculator_implements_abc_interface(
        self, calculator, two_experts_for_polymorphism
    ):
        """
        Test that BeCoMeCalculator properly inherits from and implements the ABC.

        GIVEN: BeCoMeCalculator class and test data
        WHEN: Checking inheritance and using methods polymorphically
        THEN: All ABC methods work correctly through the interface
        """
        # GIVEN: BeCoMeCalculator is a subclass of BaseAggregationCalculator
        assert issubclass(BeCoMeCalculator, BaseAggregationCalculator)

        # GIVEN: Calculator can be used polymorphically
        polymorphic_calculator: BaseAggregationCalculator = calculator

        # GIVEN: Fixture provides test opinions
        opinions = two_experts_for_polymorphism

        # WHEN: Calling abstract methods through the ABC interface
        mean = polymorphic_calculator.calculate_arithmetic_mean(opinions)
        median = polymorphic_calculator.calculate_median(opinions)
        result = polymorphic_calculator.calculate_compromise(opinions)

        # THEN: All methods return expected types
        assert isinstance(mean, FuzzyTriangleNumber)
        assert isinstance(median, FuzzyTriangleNumber)
        assert result.num_experts == 2


class TestAbstractMethodEnforcement:
    """Test that abstract methods properly enforce implementation."""

    def test_incomplete_implementation_raises_error(self):
        """
        Test that partial implementation of ABC raises TypeError.

        GIVEN: A class that only partially implements the ABC
        WHEN: Attempting to instantiate it
        THEN: TypeError is raised mentioning "abstract"
        """
        # GIVEN: Create a class that doesn't implement all abstract methods
        class IncompleteCalculator(BaseAggregationCalculator):
            def calculate_arithmetic_mean(self, opinions):
                return opinions[0].opinion

            # Missing: calculate_median, calculate_compromise, sort_by_centroid

        # WHEN/THEN: Attempting to instantiate raises TypeError
        with pytest.raises(TypeError) as exc_info:
            IncompleteCalculator()  # type: ignore

        # THEN: Error message mentions "abstract"
        assert "abstract" in str(exc_info.value).lower()


class TestBeCoMeCalculatorPublicInterface:
    """Test cases for BeCoMeCalculator public methods."""

    def test_sort_by_centroid_works_correctly(self, calculator, three_experts_for_sorting):
        """
        Test that sort_by_centroid correctly sorts opinions by centroid.

        GIVEN: Three unsorted expert opinions with different centroids
        WHEN: Calling sort_by_centroid
        THEN: Opinions are sorted in ascending order by centroid
        """
        # GIVEN: Fixture provides unsorted opinions
        # (E3: centroid=15.0, E1: centroid=2.0, E2: centroid=10.0)
        opinions = three_experts_for_sorting

        # WHEN: Sort by centroid
        sorted_opinions = calculator.sort_by_centroid(opinions)

        # THEN: Opinions are sorted by centroid (E1, E2, E3)
        assert sorted_opinions[0].expert_id == "E1"  # centroid: 2.0
        assert sorted_opinions[1].expert_id == "E2"  # centroid: 10.0
        assert sorted_opinions[2].expert_id == "E3"  # centroid: 15.0

        # THEN: Centroids are in ascending order
        centroids = [op.centroid for op in sorted_opinions]
        assert centroids == sorted(centroids)

    def test_sort_by_centroid_preserves_original_list(
        self, calculator, two_experts_for_immutability_test
    ):
        """
        Test that sort_by_centroid returns new list without modifying original.

        GIVEN: Unsorted list of opinions
        WHEN: Calling sort_by_centroid
        THEN: Original list is unchanged, new sorted list is returned
        """
        # GIVEN: Fixture provides unsorted opinions (E2, E1)
        original_opinions = two_experts_for_immutability_test

        # GIVEN: Record original order
        original_ids = [op.expert_id for op in original_opinions]

        # WHEN: Sort by centroid
        sorted_opinions = calculator.sort_by_centroid(original_opinions)

        # THEN: Original list is unchanged
        current_ids = [op.expert_id for op in original_opinions]
        assert current_ids == original_ids

        # THEN: Sorted list is different from original
        sorted_ids = [op.expert_id for op in sorted_opinions]
        assert sorted_ids != original_ids

        # THEN: Sorted list has correct order (E1, E2)
        assert sorted_ids == ["E1", "E2"]
