#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from lib import github


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
