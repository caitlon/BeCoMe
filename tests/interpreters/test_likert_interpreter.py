"""
Unit tests for Likert scale interpretation classes.

This module tests the LikertDecisionInterpreter and LikertDecision classes,
ensuring proper interpretation of fuzzy numbers using the Likert scale.
"""

import pytest

from src.interpreters.likert_interpreter import LikertDecision, LikertDecisionInterpreter
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def interpreter():
    """Fixture providing LikertDecisionInterpreter instance for tests.

    This fixture implements the GIVEN step by preparing an interpreter
    instance that can be injected into any test via Dependency Injection.
    """
    return LikertDecisionInterpreter()


class TestLikertDecision:
    """Test cases for LikertDecision value object."""

    def test_valid_creation(self):
        """Test that LikertDecision can be created with valid data."""
        # GIVEN - Valid Likert decision parameters
        likert_value = 75
        decision_text = "Rather agree"
        recommendation = "Policy is recommended"

        # WHEN - Create LikertDecision instance
        decision = LikertDecision(
            likert_value=likert_value,
            decision_text=decision_text,
            recommendation=recommendation,
        )

        # THEN - Verify all attributes are set correctly
        assert decision.likert_value == 75, (
            f"Expected likert_value to be 75, got {decision.likert_value}"
        )
        assert decision.decision_text == "Rather agree", (
            f"Expected decision_text to be 'Rather agree', got '{decision.decision_text}'"
        )
        assert decision.recommendation == "Policy is recommended", (
            f"Expected recommendation to be 'Policy is recommended', "
            f"got '{decision.recommendation}'"
        )

    def test_immutability(self):
        """Test that LikertDecision is immutable (frozen dataclass)."""
        # GIVEN - A LikertDecision instance
        decision = LikertDecision(
            likert_value=50,
            decision_text="Neutral",
            recommendation="Requires analysis",
        )

        # WHEN/THEN - Attempt to modify attribute should raise AttributeError
        with pytest.raises(AttributeError):
            decision.likert_value = 75  # type: ignore

    @pytest.mark.parametrize("value", [0, 25, 50, 75, 100])
    def test_different_likert_values(self, value):
        """Test LikertDecision with various Likert scale values."""
        # GIVEN - Likert scale value and corresponding texts
        decision_text = f"Text for {value}"
        recommendation = f"Recommendation for {value}"

        # WHEN - Create LikertDecision with the value
        decision = LikertDecision(
            likert_value=value,
            decision_text=decision_text,
            recommendation=recommendation,
        )

        # THEN - Verify the value was set correctly
        assert decision.likert_value == value, (
            f"Expected likert_value to be {value}, got {decision.likert_value}"
        )


class TestLikertDecisionInterpreter:
    """Test cases for LikertDecisionInterpreter."""

    def test_default_initialization(self, interpreter):
        """Test interpreter with default Likert scale values."""
        # GIVEN - Fuzzy number centered around 50, fixture provides interpreter
        fuzzy = FuzzyTriangleNumber(45, 50, 55)

        # WHEN - Interpret the fuzzy number
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify correct Likert value and decision text
        assert decision.likert_value == 50, (
            f"Expected likert_value to be 50, got {decision.likert_value}"
        )
        assert decision.decision_text == "Neutral", (
            f"Expected decision_text to be 'Neutral', got '{decision.decision_text}'"
        )

    def test_custom_likert_values(self):
        """Test interpreter with custom Likert scale values."""
        # GIVEN - Custom Likert scale (0, 50, 100) and interpreter configured with it
        custom_values = (0, 50, 100)
        interpreter = LikertDecisionInterpreter(likert_values=custom_values)
        fuzzy = FuzzyTriangleNumber(60, 70, 80)

        # WHEN - Interpret fuzzy number with centroid around 70
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify decision uses one of the custom values (should be 50, closest to 70)
        assert decision.likert_value in custom_values, (
            f"Expected likert_value to be in {custom_values}, got {decision.likert_value}"
        )

    @pytest.mark.parametrize(
        "lower,peak,upper,expected_value,expected_text,recommendation_keyword",
        [
            (0, 5, 10, 0, "Strongly disagree", "not recommended"),
            (20, 25, 30, 25, "Rather disagree", "revision"),
            (45, 50, 55, 50, "Neutral", "further analysis"),
            (70, 75, 80, 75, "Rather agree", "recommended"),
            (95, 100, 100, 100, "Strongly agree", "strongly recommended"),
        ],
        ids=["strongly_disagree", "rather_disagree", "neutral", "rather_agree", "strongly_agree"],
    )
    def test_interpret_all_likert_values(
        self,
        interpreter,
        lower,
        peak,
        upper,
        expected_value,
        expected_text,
        recommendation_keyword,
    ):
        """Test interpretation for all standard Likert scale values.

        This parametrized test verifies that fuzzy numbers near each
        standard Likert value (0, 25, 50, 75, 100) are correctly
        interpreted with appropriate decision text and recommendations.

        Follows DRY principle: One test instead of five duplicate tests.
        """
        # GIVEN - Fuzzy number centered around a Likert value, fixture provides interpreter
        fuzzy = FuzzyTriangleNumber(lower, peak, upper)

        # WHEN - Interpret the fuzzy number
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify correct Likert value assignment
        assert decision.likert_value == expected_value, (
            f"Expected likert_value to be {expected_value}, got {decision.likert_value}"
        )

        # THEN - Verify correct decision text
        assert decision.decision_text == expected_text, (
            f"Expected decision_text to be '{expected_text}', got '{decision.decision_text}'"
        )

        # THEN - Verify recommendation contains expected keyword
        assert recommendation_keyword in decision.recommendation.lower(), (
            f"Expected recommendation to contain '{recommendation_keyword}', "
            f"got '{decision.recommendation}'"
        )

    def test_interpret_boundary_case_between_25_and_50(self, interpreter):
        """Test interpretation at boundary between two Likert values."""
        # GIVEN - Fuzzy number with centroid exactly between 25 and 50 (37.5)
        fuzzy = FuzzyTriangleNumber(35, 37.5, 40)

        # WHEN - Interpret the boundary value
        decision = interpreter.interpret(fuzzy)

        # THEN - Should choose the closest Likert value (either 25 or 50)
        assert decision.likert_value in [25, 50], (
            f"Expected likert_value to be 25 or 50, got {decision.likert_value}"
        )

    def test_interpret_extreme_low_value(self, interpreter):
        """Test interpretation with very low fuzzy number."""
        # GIVEN - Very low fuzzy number (0, 0, 5)
        fuzzy = FuzzyTriangleNumber(0, 0, 5)

        # WHEN - Interpret the extreme low value
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify it maps to lowest Likert value
        assert decision.likert_value == 0, (
            f"Expected likert_value to be 0, got {decision.likert_value}"
        )
        assert decision.decision_text == "Strongly disagree", (
            f"Expected decision_text 'Strongly disagree', got '{decision.decision_text}'"
        )

    def test_interpret_extreme_high_value(self, interpreter):
        """Test interpretation with very high fuzzy number."""
        # GIVEN - Very high fuzzy number (95, 100, 100)
        fuzzy = FuzzyTriangleNumber(95, 100, 100)

        # WHEN - Interpret the extreme high value
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify it maps to highest Likert value
        assert decision.likert_value == 100, (
            f"Expected likert_value to be 100, got {decision.likert_value}"
        )
        assert decision.decision_text == "Strongly agree", (
            f"Expected decision_text 'Strongly agree', got '{decision.decision_text}'"
        )

    def test_interpret_returns_likert_decision_object(self, interpreter):
        """Test that interpret() returns a LikertDecision instance."""
        # GIVEN - Any fuzzy number
        fuzzy = FuzzyTriangleNumber(50, 60, 70)

        # WHEN - Interpret the fuzzy number
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify correct type and attributes
        assert isinstance(decision, LikertDecision), (
            f"Expected LikertDecision instance, got {type(decision)}"
        )
        assert hasattr(decision, "likert_value"), "Missing attribute: likert_value"
        assert hasattr(decision, "decision_text"), "Missing attribute: decision_text"
        assert hasattr(decision, "recommendation"), "Missing attribute: recommendation"

    @pytest.mark.parametrize(
        "lower,peak,upper,expected_value",
        [
            (0, 10, 20, 0),
            (80, 90, 100, 100),
        ],
        ids=["low_value_interpretation", "high_value_interpretation"],
    )
    def test_interpretations_are_independent(self, interpreter, lower, peak, upper, expected_value):
        """Test that interpreter produces correct results for different inputs.

        Follows Single Responsibility: One test, one action (interpretation).
        Previously this was one test with two WHEN blocks - now parametrized.
        """
        # GIVEN - Fuzzy number, fixture provides interpreter
        fuzzy = FuzzyTriangleNumber(lower, peak, upper)

        # WHEN - Interpret the fuzzy number
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify correct Likert value
        assert decision.likert_value == expected_value, (
            f"Expected likert_value to be {expected_value}, got {decision.likert_value}"
        )


class TestLikertInterpreterIntegration:
    """Integration tests for LikertDecisionInterpreter."""

    def test_interpret_pendlers_case_scenario(self, interpreter):
        """Test interpretation similar to Pendlers case (around 65-70)."""
        # GIVEN - Fuzzy number similar to Pendlers case result (centroid = 67.5)
        fuzzy = FuzzyTriangleNumber(60, 67.5, 75)

        # WHEN - Interpret the fuzzy number
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify it maps to either 50 or 75 (likely 75)
        assert decision.likert_value in [50, 75], (
            f"Expected likert_value to be 50 or 75, got {decision.likert_value}"
        )
        assert isinstance(decision.decision_text, str), (
            f"Expected decision_text to be string, got {type(decision.decision_text)}"
        )
        assert isinstance(decision.recommendation, str), (
            f"Expected recommendation to be string, got {type(decision.recommendation)}"
        )

    @pytest.mark.parametrize("value", [0, 25, 50, 75, 100])
    def test_all_standard_likert_values_covered(self, interpreter, value):
        """Test that all standard Likert values have proper interpretations.

        This test verifies that fuzzy numbers centered exactly on each
        standard Likert value are correctly interpreted with non-empty
        decision text and recommendations.
        """
        # GIVEN - Fuzzy number centered on a standard Likert value
        fuzzy = FuzzyTriangleNumber(value - 2, value, value + 2)

        # WHEN - Interpret the fuzzy number
        decision = interpreter.interpret(fuzzy)

        # THEN - Verify correct mapping and non-empty strings
        assert decision.likert_value == value, (
            f"Expected likert_value to be {value}, got {decision.likert_value}"
        )
        assert len(decision.decision_text) > 0, (
            f"Expected non-empty decision_text for value {value}"
        )
        assert len(decision.recommendation) > 0, (
            f"Expected non-empty recommendation for value {value}"
        )
