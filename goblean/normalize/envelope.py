"""Canonical event envelope helpers.

Functions here convert raw platform telemetry into a shared
schema that downstream modules can operate on.
"""

from __future__ import annotations

from typing import Any, Dict


def _list_to_dict(items: Any) -> Dict[str, Any]:
    """Convert a list of ``{"name": .., "value": ..}`` pairs to a dict.

    The helper is tolerant of slightly malformed inputs: entries lacking the
    expected keys are ignored rather than raising errors.  Non-list inputs
    produce an empty dictionary.
    """

    if not isinstance(items, list):
        return {}
    result: Dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if name is not None and value is not None:
            result[name] = value
    return result


def canonical_envelope(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a minimal canonical representation of ``raw_event``.

    The function expects a structure resembling a HAR request entry.  It pulls
    out common fields (``url``, ``method``, headers and query parameters) into a
    simplified dictionary so downstream modules can operate on a consistent
    schema regardless of the original telemetry source.
    """

    request = raw_event.get("request", {}) if isinstance(raw_event, dict) else {}
    envelope: Dict[str, Any] = {
        "url": request.get("url"),
        "method": request.get("method"),
        "headers": _list_to_dict(request.get("headers", [])),
        "params": _list_to_dict(request.get("queryString", [])),
    }

    post = request.get("postData")
    if isinstance(post, dict):
        text = post.get("text")
        if text is not None:
            envelope["body"] = text

    return envelope

