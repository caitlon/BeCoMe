"""add domain check constraints

Revision ID: 189d6f6fea7b
Revises: aa746657b289
Create Date: 2026-05-30 15:01:48.564919

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "189d6f6fea7b"
down_revision: str | Sequence[str] | None = "aa746657b289"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (constraint name, table, boolean condition). These mirror the Pydantic model
# validators so the database enforces the same domain invariants independently
# of the application layer.
_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("ck_projects_scale_order", "projects", "scale_min < scale_max"),
    (
        "ck_expert_opinions_fuzzy_order",
        "expert_opinions",
        "lower_bound <= peak AND peak <= upper_bound",
    ),
    (
        "ck_calculation_results_best_compromise_order",
        "calculation_results",
        "best_compromise_lower <= best_compromise_peak "
        "AND best_compromise_peak <= best_compromise_upper",
    ),
    (
        "ck_calculation_results_arithmetic_mean_order",
        "calculation_results",
        "arithmetic_mean_lower <= arithmetic_mean_peak "
        "AND arithmetic_mean_peak <= arithmetic_mean_upper",
    ),
    (
        "ck_calculation_results_median_order",
        "calculation_results",
        "median_lower <= median_peak AND median_peak <= median_upper",
    ),
    ("ck_calculation_results_num_experts_positive", "calculation_results", "num_experts > 0"),
    (
        "ck_calculation_results_likert_range",
        "calculation_results",
        "likert_value IS NULL OR (likert_value >= 0 AND likert_value <= 100)",
    ),
)


def upgrade() -> None:
    """Add domain CHECK constraints enforcing fuzzy ordering and value ranges."""
    for name, table, condition in _CHECKS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    """Drop the domain CHECK constraints."""
    for name, table, _condition in reversed(_CHECKS):
        op.drop_constraint(name, table, type_="check")
