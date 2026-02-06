# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from lib import git


class TestParseVersion(unittest.TestCase):

    def test_parse_version(self) -> None:
        self.assertEqual(git.parse_version("v1.2.3"), git.Version(1, 2, 3, None))
        self.assertEqual(git.parse_version("v1.2.3-rc.1"), git.Version(1, 2, 3, 1))

    def test_comparison(self) -> None:
        self.assertLess(git.parse_version("v1.2.3"), git.parse_version("v1.2.4"))
        self.assertLess(git.parse_version("v1.2.3"), git.parse_version("v1.3.0"))
        self.assertLess(git.parse_version("v1.2.3"), git.parse_version("v2.0.0"))
        self.assertLess(
            git.parse_version("v1.2.3-rc.1"), git.parse_version("v1.2.3-rc.2")
        )
        self.assertLess(git.parse_version("v1.2.3-rc.1"), git.parse_version("v1.2.3"))
        self.assertGreater(git.parse_version("v1.2.3"), git.parse_version("v1.2.2"))
        self.assertGreater(
            git.parse_version("v1.2.3"), git.parse_version("v1.2.3-rc.1")
        )
        self.assertEqual(git.parse_version("v1.2.3"), git.parse_version("v1.2.3"))
        self.assertEqual(
            git.parse_version("v1.2.3-rc.1"), git.parse_version("v1.2.3-rc.1")
        )
        self.assertNotEqual(git.parse_version("v1.2.3"), git.parse_version("v1.2.4"))


if __name__ == "__main__":
    unittest.main()
