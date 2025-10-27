"""
Unit tests for Likert scale interpretation classes.

This module tests the LikertDecisionInterpreter and LikertDecision classes,
ensuring proper interpretation of fuzzy numbers using the Likert scale.
"""

import pytest

from src.interpreters.likert_interpreter import LikertDecision, LikertDecisionInterpreter
from src.models.fuzzy_number import FuzzyTriangleNumber


class TestLikertDecision:
    """Test cases for LikertDecision value object."""

    def test_valid_creation(self):
        """Test that LikertDecision can be created with valid data."""
        decision = LikertDecision(
            likert_value=75,
            decision_text="Rather agree",
            recommendation="Policy is recommended",
        )

        assert decision.likert_value == 75
        assert decision.decision_text == "Rather agree"
        assert decision.recommendation == "Policy is recommended"

    def test_immutability(self):
        """Test that LikertDecision is immutable (frozen dataclass)."""
        decision = LikertDecision(
            likert_value=50,
            decision_text="Neutral",
            recommendation="Requires analysis",
        )

        with pytest.raises(AttributeError):
            decision.likert_value = 75  # type: ignore

    def test_different_likert_values(self):
        """Test LikertDecision with various Likert scale values."""
        for value in [0, 25, 50, 75, 100]:
            decision = LikertDecision(
                likert_value=value,
                decision_text=f"Text for {value}",
                recommendation=f"Recommendation for {value}",
            )
            assert decision.likert_value == value


class TestLikertDecisionInterpreter:
    """Test cases for LikertDecisionInterpreter."""

    def test_default_initialization(self):
        """Test interpreter with default Likert scale values."""
        interpreter = LikertDecisionInterpreter()

        # Test with fuzzy number centered around 50
        fuzzy = FuzzyTriangleNumber(45, 50, 55)
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 50
        assert decision.decision_text == "Neutral"

    def test_custom_likert_values(self):
        """Test interpreter with custom Likert scale values."""
        custom_values = (0, 50, 100)
        interpreter = LikertDecisionInterpreter(likert_values=custom_values)

        fuzzy = FuzzyTriangleNumber(60, 70, 80)
        decision = interpreter.interpret(fuzzy)

        # Should choose between 0, 50, 100 - closest to 70 is 50
        assert decision.likert_value in custom_values

    def test_interpret_strongly_disagree(self):
        """Test interpretation for value close to 0 (Strongly disagree)."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(0, 5, 10)  # centroid = 5
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 0
        assert decision.decision_text == "Strongly disagree"
        assert "not recommended" in decision.recommendation.lower()

    def test_interpret_rather_disagree(self):
        """Test interpretation for value close to 25 (Rather disagree)."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(20, 25, 30)  # centroid = 25
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 25
        assert decision.decision_text == "Rather disagree"
        assert "revision" in decision.recommendation.lower()

    def test_interpret_neutral(self):
        """Test interpretation for value close to 50 (Neutral)."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(45, 50, 55)  # centroid = 50
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 50
        assert decision.decision_text == "Neutral"
        assert "further analysis" in decision.recommendation.lower()

    def test_interpret_rather_agree(self):
        """Test interpretation for value close to 75 (Rather agree)."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(70, 75, 80)  # centroid = 75
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 75
        assert decision.decision_text == "Rather agree"
        assert "recommended" in decision.recommendation.lower()

    def test_interpret_strongly_agree(self):
        """Test interpretation for value close to 100 (Strongly agree)."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(95, 100, 100)  # centroid ≈ 98.33
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 100
        assert decision.decision_text == "Strongly agree"
        assert "strongly recommended" in decision.recommendation.lower()

    def test_interpret_boundary_case_between_25_and_50(self):
        """Test interpretation at boundary between two Likert values."""
        interpreter = LikertDecisionInterpreter()
        # Centroid exactly between 25 and 50 = 37.5
        # Should choose the closest one
        fuzzy = FuzzyTriangleNumber(35, 37.5, 40)
        decision = interpreter.interpret(fuzzy)

        # Should be either 25 or 50
        assert decision.likert_value in [25, 50]

    def test_interpret_extreme_low_value(self):
        """Test interpretation with very low fuzzy number."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(0, 0, 5)
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 0
        assert decision.decision_text == "Strongly disagree"

    def test_interpret_extreme_high_value(self):
        """Test interpretation with very high fuzzy number."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(95, 100, 100)
        decision = interpreter.interpret(fuzzy)

        assert decision.likert_value == 100
        assert decision.decision_text == "Strongly agree"

    def test_interpret_returns_likert_decision_object(self):
        """Test that interpret() returns a LikertDecision instance."""
        interpreter = LikertDecisionInterpreter()
        fuzzy = FuzzyTriangleNumber(50, 60, 70)
        decision = interpreter.interpret(fuzzy)

        assert isinstance(decision, LikertDecision)
        assert hasattr(decision, "likert_value")
        assert hasattr(decision, "decision_text")
        assert hasattr(decision, "recommendation")

    def test_multiple_interpretations_are_independent(self):
        """Test that multiple interpretations produce correct results."""
        interpreter = LikertDecisionInterpreter()

        fuzzy1 = FuzzyTriangleNumber(0, 10, 20)  # Should be 0
        fuzzy2 = FuzzyTriangleNumber(80, 90, 100)  # Should be 100

        decision1 = interpreter.interpret(fuzzy1)
        decision2 = interpreter.interpret(fuzzy2)

        assert decision1.likert_value == 0
        assert decision2.likert_value == 100
        assert decision1 != decision2


class TestLikertInterpreterIntegration:
    """Integration tests for LikertDecisionInterpreter."""

    def test_interpret_pendlers_case_scenario(self):
        """Test interpretation similar to Pendlers case (around 65-70)."""
        interpreter = LikertDecisionInterpreter()
        # Similar to Pendlers case result
        fuzzy = FuzzyTriangleNumber(60, 67.5, 75)  # centroid = 67.5
        decision = interpreter.interpret(fuzzy)

        # Should be either 50 or 75, likely 75
        assert decision.likert_value in [50, 75]
        assert isinstance(decision.decision_text, str)
        assert isinstance(decision.recommendation, str)

    def test_all_standard_likert_values_covered(self):
        """Test that all standard Likert values have proper interpretations."""
        interpreter = LikertDecisionInterpreter()
        likert_values = [0, 25, 50, 75, 100]

        for value in likert_values:
            fuzzy = FuzzyTriangleNumber(value - 2, value, value + 2)
            decision = interpreter.interpret(fuzzy)

            assert decision.likert_value == value
            assert len(decision.decision_text) > 0
            assert len(decision.recommendation) > 0
