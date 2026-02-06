# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import unittest

from lib.github import CheckRun, Issue, Milestone, PullRequest


class TestGitHubParsing(unittest.TestCase):
    def test_milestone_from_json(self) -> None:
        data = {
            "title": "v1.0.0",
            "number": 42,
            "html_url": "https://github.com/owner/repo/milestone/42",
        }
        ms = Milestone.fromJSON(data)
        self.assertEqual(ms.title, "v1.0.0")
        self.assertEqual(ms.number, 42)
        self.assertEqual(ms.html_url, "https://github.com/owner/repo/milestone/42")

    def test_issue_from_json(self) -> None:
        data = {
            "title": "Issue title",
            "body": "Issue body",
            "user": {"login": "alice"},
            "assignees": [{"login": "bob"}, {"login": "charlie"}],
            "number": 123,
            "html_url": "https://github.com/owner/repo/issues/123",
            "state": "open",
            "milestone": {"number": 1},
        }
        issue = Issue.fromJSON(data)
        self.assertEqual(issue.title, "Issue title")
        self.assertEqual(issue.user, "alice")
        self.assertEqual(issue.assignees, ["bob", "charlie"])
        self.assertEqual(issue.milestone, 1)

    def test_pr_from_json(self) -> None:
        data = {
            "title": "PR title",
            "body": "PR body",
            "number": 456,
            "node_id": "MDExOlB1bGxSZXF1ZXN0MTIzNDU2Nzg5",
            "html_url": "https://github.com/owner/repo/pull/456",
            "state": "closed",
            "head": {"sha": "deadbeef"},
            "milestone": None,
            "draft": False,
            "merged_at": "2025-01-01T00:00:00Z",
        }
        pr = PullRequest.fromJSON(data)
        self.assertEqual(pr.title, "PR title")
        self.assertEqual(pr.head_sha, "deadbeef")
        self.assertIsNone(pr.milestone)
        self.assertTrue(pr.merged)

    def test_check_run_from_json(self) -> None:
        data = {
            "id": 789,
            "name": "test-job",
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://github.com/owner/repo/runs/789",
        }
        cr = CheckRun.fromJSON(data)
        self.assertEqual(cr.id, 789)
        self.assertEqual(cr.conclusion, "success")


if __name__ == "__main__":
    unittest.main()
