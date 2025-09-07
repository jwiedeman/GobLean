from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import goblean.dictionary as d


def test_unknown_stable_params_filters_correctly() -> None:
    dictionary = {
        "param1": {"seen": 1000, "stability": 0.95},
        "param2": {"seen": 400, "stability": 0.97},  # too few sessions
        "param3": {"seen": 600, "stability": 0.85},  # unstable
        "param4": {"seen": 700, "stability": 0.98},  # known
    }
    known = {"param4"}

    result = d.unknown_stable_params(dictionary, known)
    assert result == ["param1"]


def test_update_dictionary_tracks_seen_and_stability() -> None:
    dictionary = d.new_dictionary()

    d.update_dictionary(dictionary, {"foo": "a"})
    d.update_dictionary(dictionary, {"foo": "a"})
    d.update_dictionary(dictionary, {"foo": "b"})

    assert dictionary["foo"]["seen"] == 3
    assert dictionary["foo"]["stability"] == 2 / 3


def test_dictionary_roundtrip(tmp_path: Path) -> None:
    dictionary = d.new_dictionary()
    d.update_dictionary(dictionary, {"foo": "bar"})

    path = tmp_path / "dict.json"
    d.save_dictionary(dictionary, path)

    loaded = d.load_dictionary(path)
    assert loaded == {
        "foo": {
            "seen": 1,
            "value_counts": {"bar": 1},
            "stability": 1.0,
        }
    }
