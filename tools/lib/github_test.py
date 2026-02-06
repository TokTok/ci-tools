#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from unittest.mock import patch

from lib import github


class TestGitHubReleases(unittest.TestCase):
    def setUp(self) -> None:
        self.gh = github.GitHub()

    def test_release_assets_not_found(self) -> None:
        with patch.object(
            self.gh, "repository", return_value="owner/repo"
        ), patch.object(self.gh, "api", return_value=[]):
            assets = self.gh.release_assets("v1.0.0")
            self.assertEqual(assets, [])

    def test_release_is_published_not_found(self) -> None:
        with patch.object(
            self.gh, "repository", return_value="owner/repo"
        ), patch.object(self.gh, "api", return_value=[]):
            self.assertFalse(self.gh.release_is_published("v1.0.0"))


class TestMarkdownPatcher(unittest.TestCase):
    def test_patch_new_section(self) -> None:
        body = "### Release notes\nNotes here."
        header = "### Release progress"
        content = "- [ ] Task 1"
        expected = (
            "### Release progress\n- [ ] Task 1\n\n### Release notes\nNotes here.\n"
        )
        self.assertEqual(github.patch_markdown_section(body, header, content), expected)

    def test_patch_existing_section(self) -> None:
        body = "### Release progress\nOld content\n\n### Release notes\nNotes here."
        header = "### Release progress"
        content = "- [x] Task 1"
        expected = (
            "### Release progress\n- [x] Task 1\n\n### Release notes\nNotes here.\n"
        )
        self.assertEqual(github.patch_markdown_section(body, header, content), expected)

    def test_patch_middle_section(self) -> None:
        body = "### Section 1\nContent 1\n\n### Section 2\nContent 2\n\n### Section 3\nContent 3"
        header = "### Section 2"
        content = "New Content 2"
        expected = "### Section 1\nContent 1\n\n### Section 2\nNew Content 2\n\n### Section 3\nContent 3\n"
        self.assertEqual(github.patch_markdown_section(body, header, content), expected)

    def test_patch_end_section(self) -> None:
        body = "### Section 1\nContent 1\n\n### Section 2\nContent 2"
        header = "### Section 2"
        content = "New Content 2"
        expected = "### Section 1\nContent 1\n\n### Section 2\nNew Content 2\n"
        self.assertEqual(github.patch_markdown_section(body, header, content), expected)


if __name__ == "__main__":
    unittest.main()
