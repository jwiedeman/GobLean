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


def test_fingerprint_header_case_insensitive():
    """Header keys should be matched regardless of case."""
    event = {
        "headers": {
            "user-agent": "Android/10",
            "x-sdk-name": "hb-api",
            "x-sdk-version": "1.2.3",
        }
    }
    assert fingerprint(event) == ("android", "hb-api", (1, 2, 3))
