import json
import subprocess
import sys
from pathlib import Path


def test_schema_check_accepts_valid_envelope(tmp_path: Path) -> None:
    env = {"url": "https://example.com", "method": "GET", "headers": {}, "params": {}}
    path = tmp_path / "env.jsonl"
    path.write_text(json.dumps(env) + "\n")
    result = subprocess.run(
        [sys.executable, "-m", "goblean.schema_check", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Validated 1 envelopes" in result.stdout


def test_schema_check_rejects_invalid_envelope(tmp_path: Path) -> None:
    env = {"url": "https://example.com"}
    path = tmp_path / "env.jsonl"
    path.write_text(json.dumps(env) + "\n")
    result = subprocess.run(
        [sys.executable, "-m", "goblean.schema_check", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
