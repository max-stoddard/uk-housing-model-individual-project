from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.python.helpers.common.paths import (
    default_was_output_dir,
    ensure_output_dir,
    resolve_output_path,
)


class TestCommonPaths(unittest.TestCase):
    def test_default_was_output_dir_points_to_repo_tmp_was(self) -> None:
        expected = Path(__file__).resolve().parents[3] / "tmp" / "was"
        self.assertEqual(default_was_output_dir(), expected)

    def test_ensure_output_dir_uses_default_dir_when_output_dir_missing(self) -> None:
        output_dir = ensure_output_dir(None, default_dir=default_was_output_dir())
        self.assertEqual(output_dir, default_was_output_dir())
        self.assertTrue(output_dir.is_dir())

    def test_explicit_output_dir_overrides_default_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            explicit_dir = Path(tmpdir) / "explicit"
            default_dir = Path(tmpdir) / "default"
            output_dir = ensure_output_dir(explicit_dir, default_dir=default_dir)
            self.assertEqual(output_dir, explicit_dir)
            self.assertTrue(output_dir.is_dir())
            self.assertFalse(default_dir.exists())

    def test_resolve_output_path_creates_default_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_dir = Path(tmpdir) / "nested" / "output"
            output_path = Path(
                resolve_output_path(
                    "example.csv",
                    output_dir=None,
                    default_dir=default_dir,
                )
            )
            self.assertEqual(output_path, default_dir / "example.csv")
            self.assertTrue(default_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
