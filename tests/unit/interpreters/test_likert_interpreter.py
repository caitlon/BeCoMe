"""Unit tests for Likert scale interpretation classes."""

import pytest

from src.interpreters.likert_interpreter import LikertDecision, LikertDecisionInterpreter
from src.models.fuzzy_number import FuzzyTriangleNumber


@pytest.fixture
def interpreter():
    """Fixture providing LikertDecisionInterpreter instance for tests.

    :return: LikertDecisionInterpreter instance
    """
    return LikertDecisionInterpreter()


class TestLikertDecision:
    """Test cases for LikertDecision value object."""

    def test_valid_creation(self):
        """Test that LikertDecision can be created with valid data."""
        # GIVEN
        likert_value = 75
        decision_text = "Rather agree"
        recommendation = "Policy is recommended"

        # WHEN
        decision = LikertDecision(
            likert_value=likert_value,
            decision_text=decision_text,
            recommendation=recommendation,
        )

        # THEN
        assert decision.likert_value == 75
        assert decision.decision_text == "Rather agree"
        assert decision.recommendation == "Policy is recommended"

    def test_immutability(self):
        """Test that LikertDecision is immutable (frozen dataclass)."""
        # GIVEN
        decision = LikertDecision(
            likert_value=50,
            decision_text="Neutral",
            recommendation="Requires analysis",
        )

        # WHEN / THEN
        with pytest.raises(AttributeError):
            decision.likert_value = 75  # type: ignore

    @pytest.mark.parametrize("value", [0, 25, 50, 75, 100])
    def test_different_likert_values(self, value):
        """Test LikertDecision with various Likert scale values."""
        # GIVEN
        decision_text = f"Text for {value}"
        recommendation = f"Recommendation for {value}"

        # WHEN
        decision = LikertDecision(
            likert_value=value,
            decision_text=decision_text,
            recommendation=recommendation,
        )

        # THEN
        assert decision.likert_value == value


class TestLikertDecisionInterpreter:
    """Test cases for LikertDecisionInterpreter."""

    def test_default_initialization(self, interpreter):
        """Test interpreter with default Likert scale values."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(45, 50, 55)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value == 50
        assert decision.decision_text == "Neutral"

    def test_custom_likert_values(self):
        """Test interpreter with custom Likert scale values."""
        # GIVEN
        custom_values = (0, 50, 100)
        interpreter = LikertDecisionInterpreter(likert_values=custom_values)
        fuzzy = FuzzyTriangleNumber(60, 70, 80)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value in custom_values

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
        """Test interpretation for all standard Likert scale values."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower, peak, upper)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value == expected_value
        assert decision.decision_text == expected_text
        assert recommendation_keyword in decision.recommendation.lower()

    def test_interpret_boundary_case_between_25_and_50(self, interpreter):
        """Test interpretation at boundary between two Likert values."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(35, 37.5, 40)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value in [25, 50]

    def test_interpret_extreme_low_value(self, interpreter):
        """Test interpretation with very low fuzzy number."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(0, 0, 5)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value == 0
        assert decision.decision_text == "Strongly disagree"

    def test_interpret_extreme_high_value(self, interpreter):
        """Test interpretation with very high fuzzy number."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(95, 100, 100)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value == 100
        assert decision.decision_text == "Strongly agree"

    def test_interpret_returns_likert_decision_object(self, interpreter):
        """Test that interpret() returns a LikertDecision instance."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(50, 60, 70)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert isinstance(decision, LikertDecision)
        assert hasattr(decision, "likert_value")
        assert hasattr(decision, "decision_text")
        assert hasattr(decision, "recommendation")

    @pytest.mark.parametrize(
        "lower,peak,upper,expected_value",
        [
            (0, 10, 20, 0),
            (80, 90, 100, 100),
        ],
        ids=["low_value_interpretation", "high_value_interpretation"],
    )
    def test_interpretations_are_independent(self, interpreter, lower, peak, upper, expected_value):
        """Test that interpreter produces correct results for different inputs."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(lower, peak, upper)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value == expected_value


class TestLikertInterpreterIntegration:
    """Integration tests for LikertDecisionInterpreter."""

    def test_interpret_pendlers_case_scenario(self, interpreter):
        """Test interpretation similar to Pendlers case."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(60, 67.5, 75)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value in [50, 75]
        assert isinstance(decision.decision_text, str)
        assert isinstance(decision.recommendation, str)

    @pytest.mark.parametrize("value", [0, 25, 50, 75, 100])
    def test_all_standard_likert_values_covered(self, interpreter, value):
        """Test that all standard Likert values have proper interpretations."""
        # GIVEN
        fuzzy = FuzzyTriangleNumber(value - 2, value, value + 2)

        # WHEN
        decision = interpreter.interpret(fuzzy)

        # THEN
        assert decision.likert_value == value
        assert len(decision.decision_text) > 0
        assert len(decision.recommendation) > 0
