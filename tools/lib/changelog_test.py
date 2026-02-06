# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from unittest.mock import mock_open, patch

from lib.changelog import ReleaseNotes, parse, set_release_notes


class TestChangelog(unittest.TestCase):
    def test_release_notes_formatted(self) -> None:
        rn = ReleaseNotes(
            version="v1.0.0",
            date="2025-01-01",
            header="### Release notes",
            notes="Note 1\nNote 2",
            changelog="#### Features\n- Feat 1",
        )
        expected = "### Release notes\n\nNote 1\nNote 2\n\n#### Features\n- Feat 1\n"
        self.assertEqual(rn.formatted(), expected)

    def test_release_notes_formatted_minimal(self) -> None:
        rn = ReleaseNotes(
            version="v1.0.0",
            date="2025-01-01",
            header="### Release notes",
            notes="",
            changelog="",
        )
        expected = "### Release notes\n"
        self.assertEqual(rn.formatted(), expected)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=(
            "## v1.0.0 (2025-01-01)\n"
            "### Release notes\n"
            "Cool notes\n"
            "#### Features\n"
            "- Feat 1\n"
            '<a name="v0.9.0"></a>\n'
            "## v0.9.0 (2024-12-01)\n"
            "### Release notes\n"
            "Older notes\n"
        ),
    )
    def test_parse(self, mock_file: unittest.mock.MagicMock) -> None:
        messages = parse("dummy.md")
        self.assertIn("v1.0.0", messages)
        self.assertEqual(messages["v1.0.0"].version, "v1.0.0")
        self.assertEqual(messages["v1.0.0"].date, "2025-01-01")
        self.assertEqual(messages["v1.0.0"].header, "### Release notes")
        self.assertEqual(messages["v1.0.0"].notes, "Cool notes")
        self.assertEqual(messages["v1.0.0"].changelog, "#### Features\n- Feat 1")

        self.assertIn("v0.9.0", messages)
        self.assertEqual(messages["v0.9.0"].notes, "Older notes")

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=("## v1.0.0 (2025-01-01)\n" "#### Features\n" "- Feat 1\n"),
    )
    def test_set_release_notes(self, mock_file: unittest.mock.MagicMock) -> None:
        set_release_notes("v1.0.0", "New notes", "dummy.md")

        # Check that the file was written with the new notes
        handle = mock_file()
        calls = handle.write.call_args_list
        written_content = "".join(call.args[0] for call in calls)

        expected_content = (
            "## v1.0.0 (2025-01-01)\n" "\nNew notes\n\n" "#### Features\n" "- Feat 1\n"
        )
        self.assertEqual(written_content, expected_content)


if __name__ == "__main__":
    unittest.main()
