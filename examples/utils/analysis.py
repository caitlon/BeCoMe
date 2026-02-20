"""Analysis utilities for BeCoMe examples."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .labels import AnalysisLabels


def calculate_agreement_level(
    max_error: float,
    thresholds: tuple[float, float] = (1.0, 3.0),
    labels: AnalysisLabels | None = None,
) -> str:
    """
    Determine expert agreement level based on maximum error.

    :param max_error: Maximum error value from BeCoMe calculation
    :param thresholds: Tuple of (good_threshold, moderate_threshold)
    :param labels: Locale-specific labels. Defaults to English.
    :return: Agreement level string: "good", "moderate", or "low"

    >>> calculate_agreement_level(0.5)
    'good'
    >>> calculate_agreement_level(2.0)
    'moderate'
    >>> calculate_agreement_level(5.0)
    'low'
    """
    if labels is None:
        from .locales import EN_ANALYSIS

        labels = EN_ANALYSIS

    good_threshold, moderate_threshold = thresholds
    if max_error < good_threshold:
        return labels.good
    elif max_error < moderate_threshold:
        return labels.moderate
    else:
        return labels.low
