#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from create_release import render_progress_list


class TestDashboardRenderer(unittest.TestCase):
    def test_render_initial_state(self) -> None:
        done: set[str] = set()
        rendered = render_progress_list(done, None, None)
        self.assertIn("[ ] Create release branch and PR", rendered)
        self.assertNotIn("**Current Step", rendered)

    def test_render_with_current_task(self) -> None:
        done = {"Preparation"}
        rendered = render_progress_list(done, "Review", "Please approve PR")
        self.assertIn("[x] Create release branch and PR", rendered)
        self.assertIn("- [ ] **Current Step: Approve and merge PR**", rendered)
        self.assertIn("> ℹ️ **Action Required:** Please approve PR", rendered)

    def test_render_all_done(self) -> None:
        done = {"Preparation", "Review", "Tagging", "Binaries", "Publication"}
        rendered = render_progress_list(done, None, None)
        self.assertIn("[x] Create release branch and PR", rendered)
        self.assertIn("[x] Approve and merge PR", rendered)
        self.assertIn("[x] Tag and sign the release", rendered)
        self.assertIn("[x] Build and sign binaries", rendered)
        self.assertIn("[x] Finalize release", rendered)


if __name__ == "__main__":
    unittest.main()
