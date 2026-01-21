"""Protocol definitions for service dependencies.

Protocols define structural interfaces for dependency injection,
allowing services to depend on abstractions rather than concrete implementations.
This follows the Dependency Inversion Principle (DIP).
"""

from typing import Protocol

from src.interpreters.likert_interpreter import LikertDecision
from src.models.become_result import BeCoMeResult
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber


class CalculatorProtocol(Protocol):
    """Protocol for expert opinion aggregation calculators.

    Any class implementing these methods can be used as a calculator,
    regardless of inheritance hierarchy.
    """

    def calculate_arithmetic_mean(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """Calculate arithmetic mean of expert opinions.

        :param opinions: List of expert opinions
        :return: Arithmetic mean as FuzzyTriangleNumber
        """
        ...

    def calculate_median(self, opinions: list[ExpertOpinion]) -> FuzzyTriangleNumber:
        """Calculate statistical median of expert opinions.

        :param opinions: List of expert opinions
        :return: Median as FuzzyTriangleNumber
        """
        ...

    def calculate_compromise(self, opinions: list[ExpertOpinion]) -> BeCoMeResult:
        """Calculate best compromise from expert opinions.

        :param opinions: List of expert opinions
        :return: Complete calculation result
        """
        ...


class LikertInterpreterProtocol(Protocol):
    """Protocol for Likert scale interpreters.

    Any class implementing the interpret method can be used,
    allowing for different interpretation strategies.
    """

    def interpret(self, fuzzy_number: FuzzyTriangleNumber) -> LikertDecision:
        """Interpret fuzzy number using Likert scale.

        :param fuzzy_number: Fuzzy triangular number to interpret
        :return: LikertDecision with interpretation results
        """
        ...
