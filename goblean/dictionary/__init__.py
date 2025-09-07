"""Dictionary of telemetry parameters."""

from collections import defaultdict
import json
from pathlib import Path
from typing import Dict, Any, Set, List


def new_dictionary() -> Dict[str, Any]:
    """Return an empty dictionary structure.

    Real implementations will track types, ranges and stability for
    each parameter.
    """
    return defaultdict(dict)


def update_dictionary(
    dictionary: Dict[str, Dict[str, Any]],
    params: Dict[str, Any],
) -> None:
    """Update *dictionary* statistics with observed *params*.

    Each parameter tracks how many times it has been seen along with a simple
    stability metric: the frequency of the most common value divided by the
    total observations.  This allows callers to identify parameters that appear
    consistently across sessions.
    """

    for name, value in params.items():
        meta = dictionary[name]

        # Increment total observations.
        meta["seen"] = meta.get("seen", 0) + 1

        # Track how often each value has been seen.
        value_counts: Dict[Any, int] = meta.setdefault("value_counts", {})
        value_counts[value] = value_counts.get(value, 0) + 1

        # Update stability as the dominant value frequency over total seen.
        meta["stability"] = max(value_counts.values()) / meta["seen"]


def unknown_stable_params(
    dictionary: Dict[str, Dict[str, Any]],
    known_set: Set[str],
    min_sessions: int = 500,
    stability: float = 0.9,
) -> List[str]:
    """Return parameters that appear stable yet unknown.

    Parameters
    ----------
    dictionary:
        Mapping of parameter name to metadata containing ``seen`` and
        ``stability`` fields.
    known_set:
        Parameters already documented.
    min_sessions:
        Minimum number of sessions a parameter must appear in.
    stability:
        Minimum observed stability value.
    """

    results: List[str] = []
    for param, meta in dictionary.items():
        if param in known_set:
            continue
        if meta.get("seen", 0) < min_sessions:
            continue
        if meta.get("stability", 0.0) < stability:
            continue
        results.append(param)
    return results


def save_dictionary(dictionary: Dict[str, Any], path: Path) -> None:
    """Serialize *dictionary* to *path* as JSON."""

    with path.open("w", encoding="utf-8") as f:
        json.dump(dictionary, f)


def load_dictionary(path: Path) -> Dict[str, Any]:
    """Load a dictionary previously saved with :func:`save_dictionary`."""

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return defaultdict(dict, data)
