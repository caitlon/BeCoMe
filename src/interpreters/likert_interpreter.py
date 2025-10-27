"""
Likert scale interpreter for fuzzy numbers.

This module provides a class for interpreting fuzzy triangular numbers
using the Likert scale (0-25-50-75-100), commonly used in survey research
and decision-making contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.fuzzy_number import FuzzyTriangleNumber


@dataclass(frozen=True)
class LikertDecision:
    """
    Decision result based on Likert scale interpretation.

    This is an immutable value object that encapsulates the interpretation
    of a fuzzy number using the Likert scale. It demonstrates the Single
    Responsibility Principle by focusing solely on representing a decision.

    Attributes:
        likert_value: Closest Likert scale value (0, 25, 50, 75, or 100)
        decision_text: Human-readable description of the decision
        recommendation: Action recommendation based on the decision

    Example:
        >>> decision = LikertDecision(
        ...     likert_value=75,
        ...     decision_text="Rather agree",
        ...     recommendation="Policy is recommended with minor adjustments"
        ... )
    """

    likert_value: int
    decision_text: str
    recommendation: str


class LikertDecisionInterpreter:
    """
    Interprets fuzzy numbers using the Likert scale for decision-making.

    This class encapsulates the business logic for interpreting fuzzy
    triangular numbers in the context of Likert scale surveys. It adheres
    to Single Responsibility Principle by focusing solely on interpretation
    logic, and Open/Closed Principle by allowing easy extension of
    interpretation rules.

    The Likert scale typically ranges from 0 to 100 with five levels:
    - 0:   Strongly disagree
    - 25:  Rather disagree
    - 50:  Neutral
    - 75:  Rather agree
    - 100: Strongly agree

    Attributes:
        _likert_values: Tuple of valid Likert scale values

    Example:
        >>> interpreter = LikertDecisionInterpreter()
        >>> fuzzy_num = FuzzyTriangleNumber(60, 70, 80)
        >>> decision = interpreter.interpret(fuzzy_num)
        >>> print(f"{decision.decision_text}: {decision.recommendation}")
        Rather agree: Policy is recommended with minor adjustments
    """

    __slots__ = ("_likert_values",)

    def __init__(self, likert_values: tuple[int, ...] | None = None) -> None:
        """
        Initialize the Likert scale interpreter.

        Args:
            likert_values: Custom Likert scale values. If None, uses standard
                          5-point scale: (0, 25, 50, 75, 100)
        """
        self._likert_values: tuple[int, ...] = likert_values or (0, 25, 50, 75, 100)

    def interpret(self, fuzzy_number: FuzzyTriangleNumber) -> LikertDecision:
        """
        Interpret a fuzzy number using the Likert scale.

        This method calculates the centroid of the fuzzy number and finds
        the closest Likert scale value, then generates appropriate decision
        text and recommendations.

        Args:
            fuzzy_number: The fuzzy triangular number to interpret

        Returns:
            LikertDecision with interpretation results

        Example:
            >>> interpreter = LikertDecisionInterpreter()
            >>> fuzzy = FuzzyTriangleNumber(70, 75, 80)
            >>> decision = interpreter.interpret(fuzzy)
            >>> decision.likert_value
            75
            >>> decision.decision_text
            'Rather agree'
        """
        # Calculate centroid and find closest Likert value
        centroid: float = fuzzy_number.centroid
        closest_value: int = min(
            self._likert_values, key=lambda x: abs(x - centroid)
        )

        # Get interpretation texts
        decision_text: str = self._get_decision_text(closest_value)
        recommendation: str = self._get_recommendation(closest_value)

        return LikertDecision(
            likert_value=closest_value,
            decision_text=decision_text,
            recommendation=recommendation,
        )

    def _get_decision_text(self, likert_value: int) -> str:
        """
        Get human-readable decision text for a Likert value.

        Args:
            likert_value: Likert scale value (0, 25, 50, 75, or 100)

        Returns:
            Decision text string

        Example:
            >>> interpreter = LikertDecisionInterpreter()
            >>> interpreter._get_decision_text(75)
            'Rather agree'
        """
        decision_map: dict[int, str] = {
            0: "Strongly disagree",
            25: "Rather disagree",
            50: "Neutral",
            75: "Rather agree",
            100: "Strongly agree",
        }

        return decision_map.get(likert_value, f"Unknown ({likert_value})")

    def _get_recommendation(self, likert_value: int) -> str:
        """
        Get action recommendation for a Likert value.

        This method encapsulates the business logic for translating
        Likert scale values into actionable recommendations.

        Args:
            likert_value: Likert scale value (0, 25, 50, 75, or 100)

        Returns:
            Recommendation text string

        Example:
            >>> interpreter = LikertDecisionInterpreter()
            >>> interpreter._get_recommendation(100)
            'Policy is strongly recommended for implementation'
        """
        recommendation_map: dict[int, str] = {
            0: "Policy is not recommended and should be rejected",
            25: "Policy needs significant revision before consideration",
            50: "Policy requires further analysis and stakeholder input",
            75: "Policy is recommended with minor adjustments",
            100: "Policy is strongly recommended for implementation",
        }

        return recommendation_map.get(
            likert_value, f"No recommendation available for value {likert_value}"
        )
