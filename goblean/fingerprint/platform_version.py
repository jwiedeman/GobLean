"""Fingerprint platforms and SDK versions from telemetry."""
from __future__ import annotations
from typing import Dict, Any, Tuple


def fingerprint(event: Dict[str, Any]) -> Tuple[str, str, Tuple[int, ...]]:
    """Infer `(platform, sdk, version)` from a normalized event.

    Returns
    -------
    platform, sdk, version
        The platform name, SDK identifier, and semantic version tuple.
    """
    # TODO: use host/path/headers/param shapes
    return "unknown", "unknown", ()
