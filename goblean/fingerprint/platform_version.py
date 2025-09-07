"""Fingerprint platforms and SDK versions from telemetry."""
from __future__ import annotations
import re
from typing import Dict, Any, Tuple


def _parse_version(text: str) -> Tuple[int, ...]:
    """Return a semantic-version tuple from *text*.

    Non-numeric components are ignored so ``"3.6.0"`` becomes ``(3, 6, 0)``
    and ``"1.2beta"`` becomes ``(1, 2)``.
    """

    parts = []
    for part in text.split('.'):
        match = re.match(r"(\d+)", part)
        if match:
            parts.append(int(match.group(1)))
        else:
            break
    return tuple(parts)


def fingerprint(event: Dict[str, Any]) -> Tuple[str, str, Tuple[int, ...]]:
    """Infer ``(platform, sdk, version)`` from a normalized event.

    The implementation is intentionally heuristic: it inspects headers commonly
    found in telemetry events.  If a field is missing the corresponding value
    defaults to ``"unknown"`` or an empty version tuple.
    """

    headers = event.get("headers", {})
    ua = headers.get("User-Agent", "").lower()

    if "roku" in ua:
        platform = "roku"
    elif "android" in ua:
        platform = "android"
    elif "ios" in ua or "iphone" in ua:
        platform = "ios"
    else:
        platform = "unknown"

    sdk = event.get("sdk") or headers.get("X-SDK-Name", "unknown")

    version_str = event.get("sdk_version") or headers.get("X-SDK-Version", "")
    version = _parse_version(version_str)

    return platform, sdk, version
