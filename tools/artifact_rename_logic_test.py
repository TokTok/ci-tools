# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from artifact_rename import _glob_to_regex


class TestArtifactRenameLogic(unittest.TestCase):
    def test_glob_to_regex_star(self) -> None:
        original = "app-*.tar.gz"
        renamed = "release-*.tar.gz"
        o_re, r_re = _glob_to_regex(original, renamed)
        self.assertEqual(o_re, "app-(.+).tar.gz")
        self.assertEqual(r_re, "release-\\1.tar.gz")

    def test_glob_to_regex_braces(self) -> None:
        original = "app-{linux,windows}.zip"
        renamed = "release-{linux,windows}.zip"
        o_re, r_re = _glob_to_regex(original, renamed)
        self.assertEqual(o_re, "app-(linux|windows).zip")
        self.assertEqual(r_re, "release-\\1.zip")

    def test_glob_to_regex_unmatched_original(self) -> None:
        # If original has a glob but renamed doesn't, it becomes a non-capturing group or matches everything
        original = "app-*.tar.gz"
        renamed = "release.tar.gz"
        o_re, r_re = _glob_to_regex(original, renamed)
        self.assertEqual(o_re, "app-.+.tar.gz")
        self.assertEqual(r_re, "release.tar.gz")


if __name__ == "__main__":
    unittest.main()
