"""Shared validators for schema validation."""

import math


def validate_fuzzy_constraints(lower: float, peak: float, upper: float) -> None:
    """Validate fuzzy triangular number constraints.

    Checks that all values are finite (not NaN or infinity) and satisfy
    the constraint: lower <= peak <= upper.

    :param lower: Lower bound value
    :param peak: Peak (most likely) value
    :param upper: Upper bound value
    :raises ValueError: If values are not finite or violate ordering constraint
    """
    values = [lower, peak, upper]
    if not all(math.isfinite(v) for v in values):
        msg = "Values must be finite (no NaN or infinity)"
        raise ValueError(msg)
    if not (lower <= peak <= upper):
        msg = f"Must satisfy: lower <= peak <= upper. Got: {lower}, {peak}, {upper}"
        raise ValueError(msg)
