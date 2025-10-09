"""
Reference test cases module from Excel implementation.

This module exports all case studies from the Excel reference implementation:
- BUDGET_CASE: 22 experts (even), COVID-19 budget support
- PENDLERS_CASE: 22 experts (even), Likert scale cross-border travel
- FLOODS_CASE: 13 experts (odd), flood prevention measures
"""

from tests.reference.budget_case import BUDGET_CASE
from tests.reference.floods_case import FLOODS_CASE
from tests.reference.pendlers_case import PENDLERS_CASE

__all__ = ["BUDGET_CASE", "FLOODS_CASE", "PENDLERS_CASE"]
