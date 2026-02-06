#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from update_changelog import Config, LogParser, group_by_category


class TestChangelogParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            changelog="CHANGELOG.md",
            production=False,
            repository="https://github.com/TokTok/ci-tools",
            forked_from=[],
            ignore_before=None,
        )
        self.parser = LogParser(self.config)

    def test_parse_feat_commit(self) -> None:
        log = [
            "a83ef30476012d3840582ddea64cf180285beb4f\n"
            "Author: Anthony Bilinski <me@abilinski.com>\n"
            "Date:   Sat Mar 5 04:20:45 2022 -0800\n"
            "\n"
            "    feat(ui): add progress dashboard\n"
            "\n"
            "    This adds a cool new dashboard to the release issue.\n"
        ]
        entries = self.parser.parse_log(log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].category, "feat")
        self.assertEqual(entries[0].module, "ui")
        self.assertEqual(entries[0].message, "add progress dashboard")

    def test_parse_fix_with_closes(self) -> None:
        log = [
            "b2215454e76012d3840582ddea64cf180285beb4f\n"
            "Author: User <user@example.com>\n"
            "Date:   Sun Mar 6 10:00:00 2022 +0000\n"
            "\n"
            "    fix: resolve crash on startup\n"
            "\n"
            "    Closes #123, fixes #456\n"
        ]
        entries = self.parser.parse_log(log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].category, "fix")
        self.assertIn("123", entries[0].closes)
        self.assertIn("456", entries[0].closes)

    def test_grouping(self) -> None:
        log = [
            "abcdef1234567890abcdef1234567890abcdef12\nAuthor: A\nDate:   Sat Mar 5 04:20:45 2022 -0800\n\n    feat: feature A",
            "abcdef1234567890abcdef1234567890abcdef13\nAuthor: A\nDate:   Sat Mar 5 04:20:45 2022 -0800\n\n    fix: fix B",
        ]
        entries = self.parser.parse_log(log)
        grouped = group_by_category(entries)
        self.assertIn("feat", grouped)
        self.assertIn("fix", grouped)
        self.assertEqual(len(grouped["feat"]), 1)


if __name__ == "__main__":
    unittest.main()
