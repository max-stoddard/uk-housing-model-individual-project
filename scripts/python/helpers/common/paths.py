"""Path helpers for script outputs."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[4]


def default_was_output_dir() -> Path:
    """Return the default output directory for WAS-generated CSV artifacts."""
    return repo_root() / "tmp" / "was"


def ensure_output_dir(
    output_dir: str | Path | None,
    default_dir: str | Path | None = None,
) -> Path:
    """Return the output directory path, creating it when needed."""
    if output_dir:
        target = Path(output_dir)
    elif default_dir:
        target = Path(default_dir)
    else:
        target = Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    return target


def resolve_output_path(
    file_name: str,
    output_dir: str | Path | None = None,
    default_dir: str | Path | None = None,
) -> str:
    """Resolve an output filename in the configured output directory."""
    return str(ensure_output_dir(output_dir, default_dir=default_dir) / file_name)
