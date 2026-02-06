# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from update_changelog import (LogEntry, category_name, escape, format_message,
                              normalize_space, parse_closes, preferred_case,
                              unindent)


class TestUpdateChangelogLogic(unittest.TestCase):
    def test_category_name(self) -> None:
        self.assertEqual(category_name("feat"), "Features")
        self.assertEqual(category_name("fix"), "Bug Fixes")
        self.assertEqual(category_name("misc"), "Miscellaneous")

    def test_unindent(self) -> None:
        text = "    line 1\n    line 2"
        self.assertEqual(unindent(text), "line 1\nline 2")

    def test_parse_closes(self) -> None:
        self.assertEqual(parse_closes("fixes #123"), ["123"])
        self.assertEqual(parse_closes("Closes #1, #2"), ["1", "2"])
        self.assertEqual(parse_closes("resolved: #42"), ["42"])
        self.assertEqual(parse_closes("no fixes here"), [])

    def test_normalize_space(self) -> None:
        self.assertEqual(normalize_space("  hello   world  "), "hello world")
        self.assertEqual(normalize_space("line\nbreak"), "line break")

    def test_preferred_case(self) -> None:
        modules = ["ui", "UI", "Ui"]
        self.assertEqual(preferred_case(modules), {None: None, "ui": "UI"})

        modules = ["Settings", "settings"]
        self.assertEqual(preferred_case(modules), {None: None, "settings": "Settings"})

    def test_escape(self) -> None:
        self.assertEqual(escape("normal"), "normal")
        self.assertEqual(escape("word_with_underscore"), "`word_with_underscore`")
        self.assertEqual(escape("std::vector"), "`std::vector`")
        self.assertEqual(escape("<tag>"), "`<tag>`")
        self.assertEqual(escape("*italic*"), "_italic_")
        self.assertEqual(escape("**bold**"), "**bold**")
        self.assertEqual(escape("*"), "\\*")
        self.assertEqual(escape("<"), "&lt;")
        self.assertEqual(escape(">"), "&gt;")

    def test_format_message(self) -> None:
        entry = LogEntry(
            repository="repo",
            sha="sha",
            author="author",
            date="date",
            category="feat",
            module="ui",
            message="Add <new> feature with *style*",
            closes=(),
        )
        self.assertEqual(format_message(entry), "Add `<new>` feature with _style_")


if __name__ == "__main__":
    unittest.main()
