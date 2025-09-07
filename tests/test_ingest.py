from pathlib import Path
import sys
import json

sys.path.append(str(Path(__file__).resolve().parents[1]))

from goblean.ingest import ingest_folder


def test_ingest_folder_parses_har(tmp_path: Path) -> None:
    sample = tmp_path / "sample.har"
    sample.write_text(json.dumps({"log": {"entries": []}}))

    results = list(ingest_folder(tmp_path))
    assert results == [{"log": {"entries": []}}]
