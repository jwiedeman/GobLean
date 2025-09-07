from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import goblean.dictionary as d


def test_unknown_stable_params_filters_correctly():
    dictionary = {
        "param1": {"seen": 1000, "stability": 0.95},
        "param2": {"seen": 400, "stability": 0.97},  # too few sessions
        "param3": {"seen": 600, "stability": 0.85},  # unstable
        "param4": {"seen": 700, "stability": 0.98},  # known
    }
    known = {"param4"}

    result = d.unknown_stable_params(dictionary, known)
    assert result == ["param1"]
