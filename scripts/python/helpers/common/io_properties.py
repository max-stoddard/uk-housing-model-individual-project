"""Helpers for Java-style key=value property files."""

from __future__ import annotations

from pathlib import Path


def read_properties(path: Path) -> dict[str, str]:
    """Read simple key=value property files, ignoring comments."""
    props: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("!"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            props[key.strip()] = value.strip()
    return props
