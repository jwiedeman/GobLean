import json
import subprocess
import sys
from pathlib import Path


def test_normalize_cli_writes_jsonl(tmp_path: Path) -> None:
    har_data = {
        "log": {
            "entries": [
                {"request": {"url": "https://example.com", "method": "GET"}}
            ]
        }
    }
    har_path = tmp_path / "sample.har"
    har_path.write_text(json.dumps(har_data))
    out_path = tmp_path / "out.jsonl"

    result = subprocess.run(
        [sys.executable, "-m", "goblean.normalize", str(har_path), str(out_path)],
        check=True,
    )
    assert result.returncode == 0
    lines = out_path.read_text().splitlines()
    assert lines
    env = json.loads(lines[0])
    assert env["url"] == "https://example.com"
    assert env["method"] == "GET"
