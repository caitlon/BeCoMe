"""Reference test cases from Excel implementation.

This module exports three case studies used for validation against Excel calculations:

BUDGET_CASE:
    22 experts (even), interval estimates for COVID-19 pandemic budget support

PENDLERS_CASE:
    22 experts (even), Likert scale ratings for cross-border travel

FLOODS_CASE:
    13 experts (odd), interval estimates for flood prevention measures

Each case contains expert opinions loaded from examples/data/ and expected results
from Excel calculations for verification of BeCoMe algorithm implementation.
"""

from tests.reference.budget_case import BUDGET_CASE
from tests.reference.floods_case import FLOODS_CASE
from tests.reference.pendlers_case import PENDLERS_CASE

__all__ = ["BUDGET_CASE", "FLOODS_CASE", "PENDLERS_CASE"]
