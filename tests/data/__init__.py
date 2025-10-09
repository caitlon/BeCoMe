"""
Test data module containing Excel reference cases.

This module exports all case studies from the Excel reference implementation:
- BUDGET_CASE: 22 experts (even), COVID-19 budget support
- PENDLERS_CASE: 22 experts (even), Likert scale cross-border travel
- FLOODS_CASE: 13 experts (odd), flood prevention measures
"""

from tests.data.budget_case import BUDGET_CASE
from tests.data.floods_case import FLOODS_CASE
from tests.data.pendlers_case import PENDLERS_CASE

__all__ = ["BUDGET_CASE", "FLOODS_CASE", "PENDLERS_CASE"]
