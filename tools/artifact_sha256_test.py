#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from artifact_sha256 import main as sha256_main


class TestArtifactSha256(unittest.TestCase):
    def test_sha256_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p = pathlib.Path(tmpdir)
            file1 = p / "test1.bin"
            file1.write_bytes(b"data1")

            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                import sys

                # Mock sha256sum output
                with patch("subprocess.check_output") as mock_run:
                    mock_run.return_value = b"deadbeef  test1.bin\n"

                    with patch.object(
                        sys, "argv", ["artifact_sha256.py", "ci-tools", "test1.bin"]
                    ):
                        sha256_main()

                sha_file = p / "test1.bin.sha256"
                self.assertTrue(sha_file.exists())
                self.assertEqual(sha_file.read_bytes(), b"deadbeef  test1.bin\n")
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
