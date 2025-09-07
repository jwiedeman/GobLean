from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from goblean.fingerprint import fingerprint


def test_fingerprint_heuristics():
    event = {
        "headers": {
            "User-Agent": "Roku/DVP-9.10", 
            "X-SDK-Name": "hb-api", 
            "X-SDK-Version": "3.6.0"
        }
    }
    assert fingerprint(event) == ("roku", "hb-api", (3, 6, 0))


def test_fingerprint_missing_fields():
    event = {}
    assert fingerprint(event) == ("unknown", "unknown", ())
