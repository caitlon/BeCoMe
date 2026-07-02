"""Shared validators for schema validation."""

import math

# Magnitude ceiling for a single fuzzy bound: generous enough for any realistic scale
# yet finite, so summing three bounds cannot overflow a float to infinity and a hostile
# payload cannot smuggle absurd magnitudes past the finite check.
MAX_ABS_FUZZY_VALUE = 1e15


def validate_fuzzy_constraints(lower: float, peak: float, upper: float) -> None:
    """Validate fuzzy triangular number constraints.

    Checks that all values are finite (not NaN or infinity), within the accepted
    magnitude, and satisfy the constraint: lower <= peak <= upper.

    :param lower: Lower bound value
    :param peak: Peak (most likely) value
    :param upper: Upper bound value
    :raises ValueError: If values are not finite, too large, or violate ordering
    """
    values = [lower, peak, upper]
    if not all(math.isfinite(v) for v in values):
        msg = "Values must be finite (no NaN or infinity)"
        raise ValueError(msg)
    if any(abs(v) > MAX_ABS_FUZZY_VALUE for v in values):
        msg = f"Values must be within +/-{MAX_ABS_FUZZY_VALUE:g}"
        raise ValueError(msg)
    if not (lower <= peak <= upper):
        msg = f"Must satisfy: lower <= peak <= upper. Got: {lower}, {peak}, {upper}"
        raise ValueError(msg)
