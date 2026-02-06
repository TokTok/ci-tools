# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from validate_pr import (parse_toxcore_version, parse_version_diff,
                         parse_weblate_prs)


class TestValidatePRLogic(unittest.TestCase):
    def test_parse_weblate_prs(self) -> None:
        prs_data = [
            {
                "title": "Translation 1",
                "html_url": "url1",
                "user": {"login": "weblate"},
            },
            {"title": "Other PR", "html_url": "url2", "user": {"login": "human"}},
            {
                "title": "Translation 2",
                "html_url": "url3",
                "user": {"login": "weblate"},
            },
        ]
        expected = [("Translation 1", "url1"), ("Translation 2", "url3")]
        self.assertEqual(parse_weblate_prs(prs_data), expected)

    def test_parse_toxcore_version(self) -> None:
        content = """#!/bin/bash
TOXCORE_VERSION=0.2.20
SOME_OTHER_VAR=val
"""
        self.assertEqual(parse_toxcore_version(content), "0.2.20")
        self.assertIsNone(parse_toxcore_version("no version here"))

    def test_parse_version_diff(self) -> None:
        diff = """--- a/platform/linux/chat.tox.CiTools.appdata.xml
+++ b/platform/linux/chat.tox.CiTools.appdata.xml
-  <release version="1.18.0-rc.3" date="2024-12-29"/>
+  <release version="1.18.0" date="2024-12-29"/>
"""
        minus, plus = parse_version_diff(diff)
        self.assertEqual(minus, ["1.18.0-rc.3"])
        self.assertEqual(plus, ["1.18.0"])

    def test_parse_version_diff_no_changes(self) -> None:
        diff = """some other changes
- <p>line</p>
+ <p>new line</p>"""
        minus, plus = parse_version_diff(diff)
        self.assertEqual(minus, [])
        self.assertEqual(plus, [])


if __name__ == "__main__":
    unittest.main()
