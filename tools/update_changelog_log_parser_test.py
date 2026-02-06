# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from update_changelog import Config, ForkInfo, LogParser


class TestLogParser(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            changelog="CHANGELOG.md",
            production=False,
            repository="https://github.com/TokTok/ci-tools",
            forked_from=[],
            ignore_before=None,
        )
        self.parser = LogParser(self.config)

    def test_parse_log_simple(self) -> None:
        log = [
            "a83ef30476012d3840582ddea64cf180285beb4f\nAuthor: Alice <alice@example.com>\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    feat(ui): add new button\n"
        ]
        entries = self.parser.parse_log(log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].sha, "a83ef30476012d3840582ddea64cf180285beb4f")
        self.assertEqual(entries[0].category, "feat")
        self.assertEqual(entries[0].module, "ui")
        self.assertEqual(entries[0].message, "add new button")

    def test_parse_log_with_merge_revert(self) -> None:
        log = [
            "a111111111111111111111111111111111111111\nAuthor: Alice\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    Merge pull request #1 from branch\n",
            'b222222222222222222222222222222222222222\nAuthor: Bob\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    Revert "feat: something"\n',
            "c333333333333333333333333333333333333333\nAuthor: Charlie\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    fix: correct logic\n",
        ]
        entries = self.parser.parse_log(log)
        # Merge and Revert should be skipped
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].sha, "c333333333333333333333333333333333333333")

    def test_parse_log_with_closes(self) -> None:
        log = [
            "d444444444444444444444444444444444444444\nAuthor: Alice\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    feat: add feature\n\n    fixes #123, closes #456\n"
        ]
        entries = self.parser.parse_log(log)
        self.assertEqual(entries[0].closes, ("123", "456"))

    def test_parse_log_with_forks(self) -> None:
        self.config.forked_from = [
            ForkInfo(repository="https://github.com/Other/repo", since="eeee")
        ]
        log = [
            "ffffffffffffffffffffffffffffffffffffffff\nAuthor: Alice\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    feat: new feat\n",
            "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\nAuthor: Alice\nDate:   Mon Jan 1 00:00:00 2025 +0000\n\n    feat: old feat\n",
        ]
        entries = self.parser.parse_log(log)
        self.assertEqual(entries[0].repository, "https://github.com/TokTok/ci-tools")
        self.assertEqual(entries[1].repository, "https://github.com/Other/repo")

    def test_parse_log_malformed(self) -> None:
        log = ["invalid log format"]
        with self.assertRaises(Exception) as cm:
            self.parser.parse_log(log)
        self.assertIn("Failed to parse log entry", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
