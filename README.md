# GobLean

Local-first telemetry specification framework.

This repository currently provides the initial scaffolding:

- Python package structure for ingesting HAR logs, normalizing events,
  fingerprinting platform/SDK versions, and running deterministic validators.
- `pyproject.toml` with core open-source dependencies.
- Minimal CLI that counts HAR files in a folder.
- Basic unit test to ensure the package imports.

Future work will implement the detailed pipeline described in `AGENTS.MD`.
