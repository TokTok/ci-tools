# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
import unittest.mock

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


class TestReleaseTags(unittest.TestCase):
    def test_release_tags_filtering(self) -> None:
        g = git.Git()
        g._run_output = unittest.mock.MagicMock(  # type: ignore
            return_value="v1.0.0\nv1.0.0-rc.1\nv1.0.0-rc.2\nv0.9.0"
        )

        # Desired behavior: v1.0.0-rc.1 and v1.0.0-rc.2 should be filtered because v1.0.0 exists
        tags = g.release_tags(with_rc=True)
        self.assertNotIn("v1.0.0-rc.1", tags)
        self.assertNotIn("v1.0.0-rc.2", tags)
        self.assertIn("v1.0.0", tags)
        self.assertIn("v0.9.0", tags)

        # RC only version should still show RCs
        g._run_output = unittest.mock.MagicMock(  # type: ignore
            return_value="v1.1.0-rc.1\nv1.0.0"
        )
        tags = g.release_tags(with_rc=True)
        self.assertIn("v1.1.0-rc.1", tags)
        self.assertIn("v1.0.0", tags)


if __name__ == "__main__":
    unittest.main()
