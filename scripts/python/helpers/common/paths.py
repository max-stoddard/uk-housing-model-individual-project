"""Path helpers for script outputs."""

from __future__ import annotations

from pathlib import Path


def ensure_output_dir(output_dir: str | None) -> Path:
    """Return the output directory path, creating it when needed."""
    target = Path(output_dir) if output_dir else Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    return target


def resolve_output_path(file_name: str, output_dir: str | None = None) -> str:
    """Resolve an output filename in the configured output directory."""
    return str(ensure_output_dir(output_dir) / file_name)
