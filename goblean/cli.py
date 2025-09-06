"""Command line interface for GobLean."""
from __future__ import annotations
import argparse
from pathlib import Path
from .ingest import ingest_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest HAR logs")
    parser.add_argument("path", type=Path, help="Folder of .har files")
    args = parser.parse_args()

    count = 0
    for _ in ingest_folder(args.path):
        count += 1
    print(f"Ingested {count} HAR files")


if __name__ == "__main__":
    main()
