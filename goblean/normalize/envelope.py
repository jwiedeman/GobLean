"""Canonical event envelope helpers.

Functions here convert raw platform telemetry into a shared
schema that downstream modules can operate on.
"""
from __future__ import annotations
from typing import Any, Dict


def canonical_envelope(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a minimal canonical representation of *raw_event*.

    This placeholder simply echoes the input; normalization logic
    will map platform-specific fields into a shared schema.
    """
    return dict(raw_event)
