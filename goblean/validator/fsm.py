"""Finite state machine based validation."""
from __future__ import annotations
from typing import Iterable, Any


class ValidationResult:
    """Result of a validation step."""

    def __init__(self, status: str, reason: str | None = None):
        self.status = status
        self.reason = reason


def evaluate(events: Iterable[Any]) -> ValidationResult:
    """Check a sequence of events for basic invariants.

    Currently verifies that the ``playhead`` parameter, when present,
    never decreases across the event stream.  If no playhead values are
    seen the validator abstains.
    """

    last_playhead: float | None = None
    seen_playhead = False
    for event in events:
        params = event.get("params", {}) if isinstance(event, dict) else {}
        ph_raw = params.get("playhead")
        if ph_raw is None:
            continue
        try:
            ph = float(ph_raw)
        except (TypeError, ValueError):
            continue
        if last_playhead is not None and ph < last_playhead:
            return ValidationResult("VIOLATION", "playhead decreased")
        last_playhead = ph
        seen_playhead = True

    if not seen_playhead:
        return ValidationResult("ABSTAIN")
    return ValidationResult("PASS")
