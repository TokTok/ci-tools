#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import os
import pathlib
import tempfile
import unittest

from artifact_rename import _glob_to_regex
from artifact_rename import main as rename_main


class TestArtifactRename(unittest.TestCase):
    def test_glob_to_regex_simple(self) -> None:
        orig = "citools-*.tar.gz"
        ren = "citools-v1.2.3.tar.gz"
        o_re, r_re = _glob_to_regex(orig, ren)
        # _glob_to_regex implementation currently only captures if '*' is in renamed
        self.assertEqual(o_re, "citools-.+.tar.gz")
        self.assertEqual(r_re, "citools-v1.2.3.tar.gz")

    def test_glob_to_regex_with_capture(self) -> None:
        orig = "citools-*.tar.gz"
        ren = "citools-v1.2.3-*.tar.gz"
        o_re, r_re = _glob_to_regex(orig, ren)
        self.assertEqual(o_re, "citools-(.+).tar.gz")
        self.assertEqual(r_re, r"citools-v1.2.3-\1.tar.gz")

    def test_end_to_end_renaming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir)
            # Create dummy files
            (p / "app-linux.tar.gz").write_text("data")
            (p / "app-windows.zip").write_text("data")

            # Change directory to temp for the test
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Mock sys.argv style input
                import sys
                from unittest.mock import patch

                original_pattern = "app-*.tar.gz app-*.zip"
                renamed_pattern = "release-*.tar.gz release-*.zip"
                files = ["app-linux.tar.gz", "app-windows.zip"]

                with patch.object(
                    sys,
                    "argv",
                    ["artifact_rename.py", original_pattern, renamed_pattern] + files,
                ):
                    rename_main()

                self.assertTrue((p / "release-linux.tar.gz").exists())
                self.assertTrue((p / "release-windows.zip").exists())
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
