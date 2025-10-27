"""
Interpreters for BeCoMe results.

This module contains classes for interpreting fuzzy numbers in various
contexts, such as Likert scale interpretation for decision-making.
"""

from .likert_interpreter import LikertDecision, LikertDecisionInterpreter

__all__ = [
    "LikertDecision",
    "LikertDecisionInterpreter",
]
