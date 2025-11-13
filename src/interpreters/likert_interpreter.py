"""Likert scale interpreter for fuzzy numbers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.fuzzy_number import FuzzyTriangleNumber


@dataclass(frozen=True)
class LikertDecision:
    """
    Decision result based on Likert scale interpretation.

    Immutable value object containing Likert interpretation results.

    :ivar likert_value: Closest Likert scale value (0, 25, 50, 75, or 100)
    :ivar decision_text: Human-readable description of the decision
    :ivar recommendation: Action recommendation based on the decision
    """

    likert_value: int
    decision_text: str
    recommendation: str


class LikertDecisionInterpreter:
    """
    Interprets fuzzy numbers using Likert scale for decision-making.

    Likert scale (0-100) with five levels:
    - 0:   Strongly disagree
    - 25:  Rather disagree
    - 50:  Neutral
    - 75:  Rather agree
    - 100: Strongly agree
    """

    __slots__ = ("_likert_values",)

    def __init__(self, likert_values: tuple[int, ...] | None = None) -> None:
        """
        Initialize Likert scale interpreter.

        :param likert_values: Custom Likert scale values.
                              Defaults to (0, 25, 50, 75, 100) if None.
        """
        self._likert_values: tuple[int, ...] = likert_values or (0, 25, 50, 75, 100)

    def interpret(self, fuzzy_number: FuzzyTriangleNumber) -> LikertDecision:
        """
        Interpret fuzzy number using Likert scale.

        Finds closest Likert value to fuzzy number's centroid and
        generates decision text and recommendation.

        :param fuzzy_number: Fuzzy triangular number to interpret
        :return: LikertDecision with interpretation results
        """
        centroid: float = fuzzy_number.centroid
        closest_value: int = min(self._likert_values, key=lambda x: abs(x - centroid))

        decision_text: str = self._get_decision_text(closest_value)
        recommendation: str = self._get_recommendation(closest_value)

        return LikertDecision(
            likert_value=closest_value,
            decision_text=decision_text,
            recommendation=recommendation,
        )

    def _get_decision_text(self, likert_value: int) -> str:
        """
        Get human-readable decision text for Likert value.

        :param likert_value: Likert scale value (0, 25, 50, 75, or 100)
        :return: Decision text string
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
        Get action recommendation for Likert value.

        :param likert_value: Likert scale value (0, 25, 50, 75, or 100)
        :return: Recommendation text string
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
