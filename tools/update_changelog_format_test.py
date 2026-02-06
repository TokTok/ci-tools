# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from typing import Optional
from unittest.mock import patch

from lib.changelog import ReleaseNotes
from update_changelog import LogEntry, format_changelog


class TestFormatChangelog(unittest.TestCase):
    @patch("update_changelog.git_tag_date", return_value="2025-01-01")
    def test_format_changelog_basic(self, mock_date: unittest.mock.MagicMock) -> None:
        tag = ("sha_v1.0.0", "v1.0.0")
        groups: dict[str, dict[Optional[str], dict[str, list[LogEntry]]]] = {
            "feat": {
                "UI": {
                    "add button": [
                        LogEntry(
                            "repo",
                            "sha1",
                            "Alice",
                            "Date",
                            "feat",
                            "UI",
                            "add button",
                            (),
                        )
                    ]
                }
            },
            "fix": {
                None: {
                    "fix crash": [
                        LogEntry(
                            "repo",
                            "sha2",
                            "Bob",
                            "Date",
                            "fix",
                            None,
                            "fix crash",
                            ("123",),
                        )
                    ]
                }
            },
        }
        old_changelog: dict[str, ReleaseNotes] = {}

        result = format_changelog(tag, groups, old_changelog)

        self.assertIn("## v1.0.0 (2025-01-01)", result)
        self.assertIn("#### Features", result)
        self.assertIn("- **UI:** add button ([sha1](repo/commit/sha1))", result)
        self.assertIn("#### Bug Fixes", result)
        self.assertIn(
            "- fix crash ([sha2](repo/commit/sha2), closes [#123](repo/issues/123))",
            result,
        )

    @patch("update_changelog.git_tag_date", return_value="2025-01-01")
    def test_format_changelog_with_notes(
        self, mock_date: unittest.mock.MagicMock
    ) -> None:
        tag = ("sha_v1.0.0", "v1.0.0")
        groups: dict[str, dict[Optional[str], dict[str, list[LogEntry]]]] = {}
        old_changelog: dict[str, ReleaseNotes] = {
            "v1.0.0": ReleaseNotes(
                "v1.0.0", "2025-01-01", "### Header", "Some notes", ""
            )
        }

        result = format_changelog(tag, groups, old_changelog)

        self.assertIn("### Header", result)
        self.assertIn("Some notes", result)

    @patch("update_changelog.git_tag_date", return_value="2025-01-01")
    def test_format_changelog_module_grouping(
        self, mock_date: unittest.mock.MagicMock
    ) -> None:
        tag = ("sha_v1.0.0", "v1.0.0")
        groups: dict[str, dict[Optional[str], dict[str, list[LogEntry]]]] = {
            "feat": {
                "Settings": {
                    "feat 1": [
                        LogEntry(
                            "repo", "sha1", "A", "D", "feat", "Settings", "feat 1", ()
                        )
                    ],
                    "feat 2": [
                        LogEntry(
                            "repo", "sha2", "B", "D", "feat", "Settings", "feat 2", ()
                        )
                    ],
                }
            }
        }
        old_changelog: dict[str, ReleaseNotes] = {}

        result = format_changelog(tag, groups, old_changelog)

        # Multiple entries for same module should be nested
        self.assertIn("- **Settings:**", result)
        self.assertIn("  - feat 1 ([sha1]", result)
        self.assertIn("  - feat 2 ([sha2]", result)


if __name__ == "__main__":
    unittest.main()
