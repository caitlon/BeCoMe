"""
Unit tests for BeCoMeCalculator.calculate_median() method.
"""

import pytest

from src.calculators.become_calculator import BeCoMeCalculator
from src.exceptions import EmptyOpinionsError
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestBeCoMeCalculatorMedian:
    """Test cases for median calculation."""

    @pytest.mark.parametrize(
        "num_experts,expected_lower,expected_peak,expected_upper",
        [
            (3, 6.0, 9.0, 12.0),  # Middle element at index 1
            (5, 7.0, 8.0, 9.0),  # Middle element at index 2
            (7, 4.0, 5.0, 6.0),  # Middle element at index 3
        ],
    )
    def test_median_with_odd_number_of_experts(
        self, num_experts, expected_lower, expected_peak, expected_upper
    ):
        """Test median with odd number of experts returns middle element."""
        if num_experts == 3:
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
        elif num_experts == 5:
            opinions = [
                ExpertOpinion(
                    expert_id=f"E{i}",
                    opinion=FuzzyTriangleNumber(
                        lower_bound=float((i - 1) * 3 + 1),
                        peak=float((i - 1) * 3 + 2),
                        upper_bound=float((i - 1) * 3 + 3),
                    ),
                )
                for i in range(1, 6)
            ]
        else:  # 7 experts
            opinions = [
                ExpertOpinion(
                    expert_id=f"E{i}",
                    opinion=FuzzyTriangleNumber(
                        lower_bound=float(i), peak=float(i + 1), upper_bound=float(i + 2)
                    ),
                )
                for i in range(1, 8)
            ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        assert result.lower_bound == expected_lower
        assert result.peak == expected_peak
        assert result.upper_bound == expected_upper

    @pytest.mark.parametrize(
        "num_experts,expected_lower,expected_peak,expected_upper",
        [
            (2, 4.5, 7.5, 10.5),  # Average of two elements
            (4, 5.5, 6.5, 7.5),  # Average of middle two (indices 1,2)
            (6, 7.0, 8.0, 9.0),  # Average of middle two (indices 2,3)
        ],
    )
    def test_median_with_even_number_of_experts(
        self, num_experts, expected_lower, expected_peak, expected_upper
    ):
        """Test median with even number of experts averages two middle elements."""
        if num_experts == 2:
            opinions = [
                ExpertOpinion(
                    expert_id="E1",
                    opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
                ),
                ExpertOpinion(
                    expert_id="E2",
                    opinion=FuzzyTriangleNumber(lower_bound=6.0, peak=9.0, upper_bound=12.0),
                ),
            ]
        elif num_experts == 4:
            opinions = [
                ExpertOpinion(
                    expert_id=f"E{i}",
                    opinion=FuzzyTriangleNumber(
                        lower_bound=float((i - 1) * 3 + 1),
                        peak=float((i - 1) * 3 + 2),
                        upper_bound=float((i - 1) * 3 + 3),
                    ),
                )
                for i in range(1, 5)
            ]
        else:  # 6 experts
            opinions = [
                ExpertOpinion(
                    expert_id=f"E{i}",
                    opinion=FuzzyTriangleNumber(
                        lower_bound=float(i * 2),
                        peak=float(i * 2 + 1),
                        upper_bound=float(i * 2 + 2),
                    ),
                )
                for i in range(1, 7)
            ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        assert result.lower_bound == expected_lower
        assert result.peak == expected_peak
        assert result.upper_bound == expected_upper

    def test_median_with_single_expert(self):
        """Test median with single expert returns same values."""
        opinion = ExpertOpinion(
            expert_id="E1",
            opinion=FuzzyTriangleNumber(lower_bound=5.0, peak=10.0, upper_bound=15.0),
        )

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median([opinion])

        # Single expert: median equals the expert's opinion
        assert result.lower_bound == 5.0
        assert result.peak == 10.0
        assert result.upper_bound == 15.0

    def test_median_empty_list_raises_error(self):
        """Test that empty opinions list raises EmptyOpinionsError."""
        calculator = BeCoMeCalculator()

        with pytest.raises(EmptyOpinionsError) as exc_info:
            calculator.calculate_median([])

        assert "empty" in str(exc_info.value).lower()

    def test_median_sorts_by_centroid(self):
        """Test that median correctly sorts opinions by centroid before calculation."""
        opinions = [
            ExpertOpinion(
                expert_id="High",
                opinion=FuzzyTriangleNumber(lower_bound=15.0, peak=18.0, upper_bound=21.0),
            ),  # centroid = 18.0
            ExpertOpinion(
                expert_id="Low",
                opinion=FuzzyTriangleNumber(lower_bound=3.0, peak=6.0, upper_bound=9.0),
            ),  # centroid = 6.0
            ExpertOpinion(
                expert_id="Mid",
                opinion=FuzzyTriangleNumber(lower_bound=9.0, peak=12.0, upper_bound=15.0),
            ),  # centroid = 12.0
        ]

        calculator = BeCoMeCalculator()
        result = calculator.calculate_median(opinions)

        # Should return middle after sorting: Mid
        assert result.lower_bound == 9.0
        assert result.peak == 12.0
        assert result.upper_bound == 15.0
