from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from goblean.normalize import canonical_envelope


def test_canonical_envelope_extracts_fields() -> None:
    raw = {
        "request": {
            "url": "https://example.com/api",
            "method": "GET",
            "headers": [
                {"name": "User-Agent", "value": "TestAgent"},
                {"name": "X-Foo", "value": "bar"},
            ],
            "queryString": [
                {"name": "a", "value": "1"},
                {"name": "b", "value": "2"},
            ],
            "postData": {"text": "body"},
        }
    }

    env = canonical_envelope(raw)
    assert env["url"] == "https://example.com/api"
    assert env["method"] == "GET"
    assert env["headers"] == {"User-Agent": "TestAgent", "X-Foo": "bar"}
    assert env["params"] == {"a": "1", "b": "2"}
    assert env["body"] == "body"


def test_canonical_envelope_parses_url_params() -> None:
    """Query parameters embedded in the URL should be extracted."""

    raw = {"request": {"url": "https://example.com/api?a=1&b=2"}}

    env = canonical_envelope(raw)
    assert env["params"] == {"a": "1", "b": "2"}


def test_canonical_envelope_handles_missing() -> None:
    """Missing sections should result in empty mappings, not errors."""

    env = canonical_envelope({})
    assert env == {"url": None, "method": None, "headers": {}, "params": {}}

