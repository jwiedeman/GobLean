"""Finite state machine based validation."""
from __future__ import annotations
from typing import Iterable, Any


class ValidationResult:
    """Result of a validation step."""

    def __init__(self, status: str, reason: str | None = None):
        self.status = status
        self.reason = reason


def evaluate(events: Iterable[Any]) -> ValidationResult:
    """Run placeholder validator over *events*.

    In the future this will implement a finite state machine and
    invariant checks. For now it always abstains.
    """
    return ValidationResult("ABSTAIN")
