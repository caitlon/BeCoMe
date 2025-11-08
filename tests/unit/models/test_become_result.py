"""
Unit tests for BeCoMeResult model.

Following Lott's "Python Object-Oriented Programming" (Chapter 13):
- Tests structured as GIVEN-WHEN-THEN
- Fixtures provide test data (Dependency Injection)
- Each test validates a single behavior
"""

import contextlib

import pytest
from pydantic import ValidationError

from src.models.become_result import BeCoMeResult
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def become_result(standard_fuzzy):
    """Fixture providing a BeCoMeResult instance for tests.

    Uses standard_fuzzy and creates a basic result with odd number of experts.
    This fixture implements the GIVEN step by preparing test data
    that can be injected into any test via Dependency Injection.
    """
    return BeCoMeResult(
        best_compromise=standard_fuzzy,
        arithmetic_mean=FuzzyTriangleNumber(4.0, 9.0, 14.0),
        median=FuzzyTriangleNumber(6.0, 11.0, 16.0),
        max_error=1.5,
        num_experts=5,
        is_even=False,
    )


class TestBeCoMeResultCreation:
    """Test cases for BeCoMeResult object creation."""

    def test_valid_creation(self):
        """Test creating a valid BeCoMeResult."""
        # GIVEN: Valid fuzzy numbers and parameters for BeCoMeResult
        best_compromise = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        arithmetic_mean = FuzzyTriangleNumber(lower_bound=4.0, peak=9.0, upper_bound=14.0)
        median = FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0)

        # WHEN: Creating a BeCoMeResult with all required fields
        result = BeCoMeResult(
            best_compromise=best_compromise,
            arithmetic_mean=arithmetic_mean,
            median=median,
            max_error=1.5,
            num_experts=5,
            is_even=False,
        )

        # THEN: Result is created with correct values
        assert result.best_compromise == best_compromise
        assert result.arithmetic_mean == arithmetic_mean
        assert result.median == median
        assert result.max_error == 1.5
        assert result.num_experts == 5
        assert result.is_even is False

    def test_creation_with_even_experts(self):
        """Test creating result with even number of experts."""
        # GIVEN/WHEN: Creating BeCoMeResult with even number of experts
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            arithmetic_mean=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            median=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            max_error=0.0,
            num_experts=4,
            is_even=True,
        )

        # THEN: is_even flag is correctly set to True
        assert result.num_experts == 4
        assert result.is_even is True

    def test_creation_with_zero_error(self):
        """Test creating result with zero max error."""
        # GIVEN/WHEN: Creating BeCoMeResult with zero max_error (identical mean and median)
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            arithmetic_mean=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            median=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            max_error=0.0,
            num_experts=3,
            is_even=False,
        )

        # THEN: max_error is correctly set to 0.0 (perfect agreement)
        assert result.max_error == 0.0


class TestBeCoMeResultStringRepresentation:
    """Test cases for string representation."""

    def test_str_representation_odd_experts(self):
        """Test __str__ method with odd number of experts."""
        # GIVEN: BeCoMeResult with odd number of experts
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            arithmetic_mean=FuzzyTriangleNumber(lower_bound=4.0, peak=9.0, upper_bound=14.0),
            median=FuzzyTriangleNumber(lower_bound=6.0, peak=11.0, upper_bound=16.0),
            max_error=1.5,
            num_experts=5,
            is_even=False,
        )

        # WHEN: Converting result to string
        str_repr = str(result)

        # THEN: String contains all important information and shows 'odd'
        assert "5 experts" in str_repr
        assert "odd" in str_repr
        assert "Best Compromise" in str_repr
        assert "Arithmetic Mean" in str_repr
        assert "Median" in str_repr
        assert "Max Error" in str_repr
        assert "1.5" in str_repr

    def test_str_representation_even_experts(self):
        """Test __str__ method with even number of experts."""
        # GIVEN: BeCoMeResult with even number of experts
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            arithmetic_mean=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            median=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
            max_error=0.0,
            num_experts=4,
            is_even=True,
        )

        # WHEN: Converting result to string
        str_repr = str(result)

        # THEN: String shows 'even' and correct values
        assert "4 experts" in str_repr
        assert "even" in str_repr
        assert "0.0" in str_repr

    def test_str_representation_contains_fuzzy_numbers(self):
        """Test that string representation includes fuzzy number values."""
        # GIVEN: BeCoMeResult with specific fuzzy number values
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(lower_bound=7.5, peak=12.3, upper_bound=18.9),
            arithmetic_mean=FuzzyTriangleNumber(lower_bound=6.5, peak=11.3, upper_bound=17.9),
            median=FuzzyTriangleNumber(lower_bound=8.5, peak=13.3, upper_bound=19.9),
            max_error=2.7,
            num_experts=7,
            is_even=False,
        )

        # WHEN: Converting result to string
        str_repr = str(result)

        # THEN: String contains fuzzy number values
        assert "7.5" in str_repr
        assert "12.3" in str_repr
        assert "18.9" in str_repr
        assert "2.7" in str_repr


class TestBeCoMeResultImmutability:
    """Test cases for immutability (frozen Pydantic model)."""

    def test_frozen_best_compromise(self):
        """Test that best_compromise cannot be modified after creation."""
        # GIVEN: A created BeCoMeResult instance
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(7.0, 10.5, 14.0),
            arithmetic_mean=FuzzyTriangleNumber(6.0, 10.0, 14.0),
            median=FuzzyTriangleNumber(8.0, 11.0, 14.0),
            max_error=1.0,
            num_experts=5,
            is_even=False,
        )

        # WHEN/THEN: Attempting to modify best_compromise raises ValidationError
        new_fuzzy = FuzzyTriangleNumber(10.0, 20.0, 30.0)
        with pytest.raises(ValidationError):
            result.best_compromise = new_fuzzy

    def test_frozen_num_experts(self):
        """Test that num_experts cannot be modified after creation."""
        # GIVEN: A created BeCoMeResult instance
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(7.0, 10.5, 14.0),
            arithmetic_mean=FuzzyTriangleNumber(6.0, 10.0, 14.0),
            median=FuzzyTriangleNumber(8.0, 11.0, 14.0),
            max_error=1.0,
            num_experts=5,
            is_even=False,
        )

        # WHEN/THEN: Attempting to modify num_experts raises ValidationError
        with pytest.raises(ValidationError):
            result.num_experts = 10

    def test_frozen_max_error(self):
        """Test that max_error cannot be modified after creation."""
        # GIVEN: A created BeCoMeResult instance
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(7.0, 10.5, 14.0),
            arithmetic_mean=FuzzyTriangleNumber(6.0, 10.0, 14.0),
            median=FuzzyTriangleNumber(8.0, 11.0, 14.0),
            max_error=1.0,
            num_experts=5,
            is_even=False,
        )

        # WHEN/THEN: Attempting to modify max_error raises ValidationError
        with pytest.raises(ValidationError):
            result.max_error = 2.0

    def test_immutable_result_integrity(self):
        """Test that BeCoMeResult maintains data integrity through immutability."""
        # GIVEN: A created BeCoMeResult instance
        result = BeCoMeResult(
            best_compromise=FuzzyTriangleNumber(7.0, 10.5, 14.0),
            arithmetic_mean=FuzzyTriangleNumber(6.0, 10.0, 14.0),
            median=FuzzyTriangleNumber(8.0, 11.0, 14.0),
            max_error=1.0,
            num_experts=5,
            is_even=False,
        )

        # Store original values
        original_num_experts = result.num_experts
        original_max_error = result.max_error

        # WHEN: Attempting to modify fields (suppressing ValidationError)
        with contextlib.suppress(ValidationError):
            result.num_experts = 100

        # THEN: Values remain unchanged (immutability preserved)
        assert result.num_experts == original_num_experts
        assert result.max_error == original_max_error


class TestBeCoMeResultFactoryMethod:
    """Test cases for BeCoMeResult.from_calculations() factory method."""

    def test_from_calculations_creates_valid_result(self):
        """Test that factory method creates a valid BeCoMeResult."""
        # GIVEN: Fuzzy numbers for mean and median
        mean = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        median = FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)

        # WHEN: Creating result from calculations
        result = BeCoMeResult.from_calculations(arithmetic_mean=mean, median=median, num_experts=5)

        # THEN: Valid BeCoMeResult is created with correct values
        assert isinstance(result, BeCoMeResult)
        assert result.arithmetic_mean == mean
        assert result.median == median
        assert result.num_experts == 5

    def test_from_calculations_calculates_best_compromise_correctly(self):
        """Test that best compromise is calculated as (mean + median) / 2."""
        # GIVEN: Fuzzy numbers for mean and median
        mean = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        median = FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)

        # WHEN: Creating result from calculations
        result = BeCoMeResult.from_calculations(arithmetic_mean=mean, median=median, num_experts=5)

        # THEN: Best compromise is calculated as (mean + median) / 2
        # π = (10 + 12) / 2 = 11.0
        # φ = (15 + 16) / 2 = 15.5
        # ξ = (20 + 22) / 2 = 21.0
        assert result.best_compromise.lower_bound == 11.0
        assert result.best_compromise.peak == 15.5
        assert result.best_compromise.upper_bound == 21.0

    def test_from_calculations_calculates_max_error_correctly(self):
        """Test that max error is calculated as |centroid(mean) - centroid(median)| / 2."""
        # GIVEN: Fuzzy numbers for mean and median
        mean = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        median = FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)

        # WHEN: Creating result from calculations
        result = BeCoMeResult.from_calculations(arithmetic_mean=mean, median=median, num_experts=5)

        # THEN: Max error is calculated as |centroid(mean) - centroid(median)| / 2
        # Mean centroid: (10 + 15 + 20) / 3 = 15.0
        # Median centroid: (12 + 16 + 22) / 3 = 16.666...
        # Max error: |15.0 - 16.666...| / 2 = 0.833...
        expected_max_error = abs(mean.centroid - median.centroid) / 2
        assert abs(result.max_error - expected_max_error) < 0.001

    def test_from_calculations_determines_is_even_correctly(self):
        """Test that is_even flag is set correctly based on num_experts."""
        # GIVEN: Fuzzy numbers for mean and median
        mean = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        median = FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)

        # WHEN: Creating result with odd number of experts
        result_odd = BeCoMeResult.from_calculations(
            arithmetic_mean=mean, median=median, num_experts=5
        )
        # THEN: is_even is False
        assert result_odd.is_even is False

        # WHEN: Creating result with even number of experts
        result_even = BeCoMeResult.from_calculations(
            arithmetic_mean=mean, median=median, num_experts=6
        )
        # THEN: is_even is True
        assert result_even.is_even is True

    def test_from_calculations_with_identical_mean_and_median(self):
        """Test factory method when mean and median are identical."""
        # GIVEN: Identical fuzzy number for both mean and median
        fuzzy = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)

        # WHEN: Creating result with identical mean and median
        result = BeCoMeResult.from_calculations(arithmetic_mean=fuzzy, median=fuzzy, num_experts=1)

        # THEN: Best compromise equals mean/median and max_error is 0
        assert result.best_compromise == fuzzy
        assert result.max_error == 0.0

    def test_from_calculations_raises_error_for_invalid_num_experts(self):
        """Test that factory method raises ValueError for num_experts < 1."""
        # GIVEN: Fuzzy numbers for mean and median
        mean = FuzzyTriangleNumber(lower_bound=10.0, peak=15.0, upper_bound=20.0)
        median = FuzzyTriangleNumber(lower_bound=12.0, peak=16.0, upper_bound=22.0)

        # WHEN/THEN: Creating result with invalid num_experts raises ValueError
        with pytest.raises(ValueError) as exc_info:
            BeCoMeResult.from_calculations(arithmetic_mean=mean, median=median, num_experts=0)

        assert "num_experts must be >= 1" in str(exc_info.value)

    def test_from_calculations_preserves_fuzzy_constraint(self):
        """Test that best compromise preserves fuzzy number constraint."""
        # GIVEN: Fuzzy numbers for mean and median
        mean = FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0)
        median = FuzzyTriangleNumber(lower_bound=7.0, peak=12.0, upper_bound=17.0)

        # WHEN: Creating result from calculations
        result = BeCoMeResult.from_calculations(arithmetic_mean=mean, median=median, num_experts=3)

        # THEN: Best compromise satisfies fuzzy constraint (lower <= peak <= upper)
        bc = result.best_compromise
        assert bc.lower_bound <= bc.peak
        assert bc.peak <= bc.upper_bound
