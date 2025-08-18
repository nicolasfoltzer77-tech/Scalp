"""Signal utilities including confluence quality mapping."""
from __future__ import annotations

__all__ = ["confluence_quality"]


def confluence_quality(score: float) -> str:
    """Return a quality grade based on ``score``.

    ``score`` must lie between 0 and 1.  Values above or equal to 0.8 map to
    grade ``"A"``, values above or equal to 0.5 to grade ``"B"`` and lower
    values to grade ``"C"``.
    """
    if not 0.0 <= score <= 1.0:
        raise ValueError("score must be between 0 and 1")
    if score >= 0.8:
        return "A"
    if score >= 0.5:
        return "B"
    return "C"
