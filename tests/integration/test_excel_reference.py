"""Integration tests for BeCoMe with Excel reference data."""

import pytest

from examples.utils.data_loading import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator
from tests.reference.budget_case import BUDGET_CASE
from tests.reference.floods_case import FLOODS_CASE
from tests.reference.pendlers_case import PENDLERS_CASE


@pytest.fixture
def calculator():
    """
    BeCoMeCalculator instance for tests.

    :return: BeCoMeCalculator instance
    """
    return BeCoMeCalculator()


class TestExcelIntegration:
    """Integration tests comparing BeCoMe calculations with Excel reference data."""

    @pytest.mark.parametrize(
        "case_name,case_data",
        [
            ("BUDGET", BUDGET_CASE),
            ("FLOODS", FLOODS_CASE),
            ("PENDLERS", PENDLERS_CASE),
        ],
    )
    def test_excel_reference_cases(self, calculator, case_name: str, case_data: dict):
        """Test all Excel reference cases with full validation."""
        # GIVEN
        expected = case_data["expected_result"]

        # WHEN
        result = calculator.calculate_compromise(case_data["opinions"])

        # THEN
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name}: Best compromise peak mismatch: "
            f"got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        if "best_compromise_lower" in expected:
            assert (
                abs(result.best_compromise.lower_bound - expected["best_compromise_lower"]) < 0.001
            ), (
                f"{case_name}: Best compromise lower mismatch: "
                f"got {result.best_compromise.lower_bound}, "
                f"expected {expected['best_compromise_lower']}"
            )

        if "best_compromise_upper" in expected:
            assert (
                abs(result.best_compromise.upper_bound - expected["best_compromise_upper"]) < 0.001
            ), (
                f"{case_name}: Best compromise upper mismatch: "
                f"got {result.best_compromise.upper_bound}, "
                f"expected {expected['best_compromise_upper']}"
            )

        if "best_compromise_centroid" in expected:
            result_centroid = result.best_compromise.centroid
            assert abs(result_centroid - expected["best_compromise_centroid"]) < 0.01, (
                f"{case_name}: Best compromise centroid mismatch: "
                f"got {result_centroid}, "
                f"expected {expected['best_compromise_centroid']}"
            )

        assert abs(result.arithmetic_mean.peak - expected["mean_peak"]) < 0.001, (
            f"{case_name}: Mean peak mismatch"
        )

        if "mean_lower" in expected:
            assert abs(result.arithmetic_mean.lower_bound - expected["mean_lower"]) < 0.001, (
                f"{case_name}: Mean lower bound mismatch"
            )

        if "mean_upper" in expected:
            assert abs(result.arithmetic_mean.upper_bound - expected["mean_upper"]) < 0.001, (
                f"{case_name}: Mean upper bound mismatch"
            )

        assert abs(result.median.lower_bound - expected["median_lower"]) < 0.001, (
            f"{case_name}: Median lower bound mismatch"
        )
        assert abs(result.median.peak - expected["median_peak"]) < 0.001, (
            f"{case_name}: Median peak mismatch"
        )
        assert abs(result.median.upper_bound - expected["median_upper"]) < 0.001, (
            f"{case_name}: Median upper bound mismatch"
        )

        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name}: Max error mismatch: "
            f"got {result.max_error}, "
            f"expected {expected['max_error']}"
        )

        assert result.num_experts == expected["num_experts"], (
            f"{case_name}: Expert count mismatch: "
            f"got {result.num_experts}, "
            f"expected {expected['num_experts']}"
        )

        if case_name == "FLOODS":
            assert result.is_even is False, f"{case_name}: Should be odd (13 experts)"
        elif case_name in ["BUDGET", "PENDLERS"]:
            assert result.is_even is True, f"{case_name}: Should be even (22 experts)"

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_txt_file_parsing(self, data_file: str, reference_case: dict, case_name: str):
        """Test text file parsing extracts correct metadata and opinions."""
        # GIVEN
        expected = reference_case["expected_result"]

        # WHEN
        opinions, metadata = load_data_from_txt(data_file)

        # THEN
        assert metadata["case"] == case_name, f"Case name mismatch in {data_file}"
        assert len(opinions) == expected["num_experts"], (
            f"Expert count mismatch in {data_file}: "
            f"got {len(opinions)}, expected {expected['num_experts']}"
        )

    @pytest.mark.parametrize(
        "data_file,reference_case,case_name",
        [
            ("examples/data/budget_case.txt", BUDGET_CASE, "Budget"),
            ("examples/data/floods_case.txt", FLOODS_CASE, "Floods"),
            ("examples/data/pendlers_case.txt", PENDLERS_CASE, "Pendlers"),
        ],
    )
    def test_full_pipeline_calculation(
        self, calculator, data_file: str, reference_case: dict, case_name: str
    ):
        """Test end-to-end pipeline: parse file and calculate results."""
        # GIVEN
        opinions, _ = load_data_from_txt(data_file)
        expected = reference_case["expected_result"]

        # WHEN
        result = calculator.calculate_compromise(opinions)

        # THEN
        assert abs(result.best_compromise.peak - expected["best_compromise_peak"]) < 0.001, (
            f"{case_name}: Best compromise peak mismatch after full pipeline: "
            f"got {result.best_compromise.peak}, "
            f"expected {expected['best_compromise_peak']}"
        )

        assert abs(result.max_error - expected["max_error"]) < 0.01, (
            f"{case_name}: Max error mismatch after full pipeline: "
            f"got {result.max_error}, "
            f"expected {expected['max_error']}"
        )

        assert result.num_experts == expected["num_experts"], (
            f"{case_name}: Expert count mismatch after full pipeline"
        )
