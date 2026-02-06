#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest
from unittest.mock import MagicMock

from create_release import Config, Releaser


class TestDashboardRenderer(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(
            branch="master",
            main_branch="master",
            dryrun=False,
            force=True,
            github_actions=True,
            issue=1,
            production=True,
            rebase=True,
            resume=False,
            verify=False,
            version="",
            upstream="origin",
        )
        self.releaser = Releaser(self.config, MagicMock(), MagicMock())

    def test_render_initial_state(self) -> None:
        done: set[str] = set()
        rendered = self.releaser.render_progress_list(done, None, None)
        self.assertIn("[ ] Create release branch and PR", rendered)
        self.assertNotIn("**Current Step", rendered)

    def test_render_with_current_task(self) -> None:
        done = {"Preparation"}
        rendered = self.releaser.render_progress_list(
            done, "Review", "Please approve PR"
        )
        self.assertIn("[x] Create release branch and PR", rendered)
        self.assertIn("- [ ] **Current Step: Approve and merge PR**", rendered)
        self.assertIn("> ℹ️ **Action Required:** Please approve PR", rendered)

    def test_render_all_done(self) -> None:
        done = {"Preparation", "Review", "Tagging", "Binaries", "Publication"}
        rendered = self.releaser.render_progress_list(done, None, None)
        self.assertIn("[x] Create release branch and PR", rendered)
        self.assertIn("[x] Approve and merge PR", rendered)
        self.assertIn("[x] Tag and sign the release", rendered)
        self.assertIn("[x] Build and sign binaries", rendered)
        self.assertIn("[x] Finalize release", rendered)


if __name__ == "__main__":
    unittest.main()
