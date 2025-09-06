"""Dictionary of telemetry parameters."""

from collections import defaultdict
from typing import Dict, Any


def new_dictionary() -> Dict[str, Any]:
    """Return an empty dictionary structure.

    Real implementations will track types, ranges and stability for
    each parameter.
    """
    return defaultdict(dict)
