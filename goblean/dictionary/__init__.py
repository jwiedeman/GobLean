"""Dictionary of telemetry parameters."""

from collections import defaultdict
from typing import Dict, Any, Set, List


def new_dictionary() -> Dict[str, Any]:
    """Return an empty dictionary structure.

    Real implementations will track types, ranges and stability for
    each parameter.
    """
    return defaultdict(dict)


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
