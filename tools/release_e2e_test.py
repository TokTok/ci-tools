#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2026 The TokTok team
import unittest
from unittest.mock import MagicMock, mock_open, patch

from create_release import Config, Releaser
from lib import git, github, stage, types


class FakeGitHub(github.GitHub):
    def __init__(self) -> None:
        self._issues: dict[int, github.Issue] = {}
        self._prs: list[github.PullRequest] = []
        self._milestones: dict[str, github.Milestone] = {}
        self._assets: list[github.ReleaseAsset] = []
        self._release_published: bool = False
        self._checks: dict[str, dict[str, github.CheckRun]] = {}
        self._action_runs: dict[str, list[github.ActionRun]] = {}

    def actor(self) -> str:
        return "bot"

    def repository(self) -> str:
        return "TokTok/ci-tools"

    def repository_name(self) -> str:
        return "ci-tools"

    def get_issue(self, number: int) -> github.Issue:
        return self._issues[number]

    def change_issue(self, number: int, changes: dict[str, str | int]) -> None:
        for k, v in changes.items():
            if k == "body" and isinstance(v, str):
                self._issues[number].body = v
            elif k == "milestone" and isinstance(v, int):
                self._issues[number].milestone = v
            elif k == "title" and isinstance(v, str):
                self._issues[number].title = v
            elif k == "state" and isinstance(v, str):
                self._issues[number].state = v

    def find_pr_for_branch(
        self, head: str, base: str, state: str = "all"
    ) -> github.PullRequest | None:
        for pr in self._prs:
            if pr.state == state or state == "all":
                return pr
        return None

    def find_pr(self, head_sha: str, base: str) -> github.PullRequest | None:
        for pr in self._prs:
            if pr.head_sha == head_sha:
                return pr
        return None

    def next_milestone(self) -> github.Milestone:
        return github.Milestone(title="v1.0.0", number=1, html_url="")

    def release_is_published(self, tag: str) -> bool:
        return self._release_published

    def release_assets(self, tag: str) -> list[github.ReleaseAsset]:
        return self._assets

    def issue_unassign(self, issue_id: int, users: list[str]) -> None:
        pass

    def issue_assign(self, issue_id: int, users: list[str]) -> None:
        pass

    def rename_issue(self, issue_id: int, title: str) -> None:
        self._issues[issue_id].title = title

    def assign_milestone(self, issue_id: int, milestone: int) -> None:
        self._issues[issue_id].milestone = milestone

    def milestone(self, title: str) -> github.Milestone:
        return github.Milestone(title=title, number=1, html_url="")

    def create_pr(
        self, title: str, body: str, head: str, base: str, milestone: int
    ) -> github.PullRequest:
        pr = github.PullRequest(
            title=title,
            body=body,
            number=123,
            node_id="node",
            html_url="url",
            state="open",
            head_sha="sha123",
            milestone=milestone,
            draft=True,
            merged=False,
        )
        self._prs.append(pr)
        return pr

    def release_candidates(self, version: str) -> list[int]:
        return []

    def latest_release(self) -> str:
        return "v0.9.0"

    def prereleases(self, version: str) -> list[str]:
        return []

    def action_runs(self, branch: str, sha: str) -> list[github.ActionRun]:
        return self._action_runs.get(sha, [])

    def checks(self, sha: str) -> dict[str, github.CheckRun]:
        return self._checks.get(sha, {})

    def change_pr(self, number: int, changes: dict[str, str | int]) -> None:
        for pr in self._prs:
            if pr.number == number:
                for k, v in changes.items():
                    if k == "state" and isinstance(v, str):
                        pr.state = v
                    elif k == "merged" and isinstance(v, bool):
                        pr.merged = v

    def open_milestone_issues(self, milestone: int) -> list[github.Issue]:
        return [
            i
            for i in self._issues.values()
            if i.milestone == milestone and i.state == "open"
        ]

    def mark_ready_for_review(self, pr_node_id: str) -> None:
        for pr in self._prs:
            if pr.node_id == pr_node_id:
                pr.draft = False

    def release_id(self, tag: str) -> int:
        return 1

    def set_release_notes(self, tag: str, notes: str, prerelease: bool) -> None:
        pass

    def close_milestone(self, number: int) -> None:
        pass

    def close_issue(self, number: int) -> None:
        self._issues[number].state = "closed"

    def tag(
        self, slug: types.RepoSlug, commit_sha: str, tag_name: str, tag_message: str
    ) -> str:
        return "sha_tag"

    def clear_cache(self) -> None:
        pass


class FakeGit(git.Git):
    def __init__(self) -> None:
        self._branches: list[str] = ["master"]
        self._current_branch: str = "master"
        self._tags: list[str] = []
        self._log: list[str] = ["initial commit"]

    def current_branch(self) -> str:
        return self._current_branch

    def branches(self, remote: str | None = None) -> list[str]:
        return self._branches

    def log(self, branch: str, count: int = 100) -> list[str]:
        return self._log

    def is_clean(self) -> bool:
        return True

    def branch_sha(self, branch: str) -> str:
        return "sha123"

    def find_commit_sha(self, msg: str) -> str:
        return "sha123"

    def release_tag_exists(self, tag: str) -> bool:
        return tag in self._tags

    def tag_has_signature(self, tag: str) -> bool:
        return True

    def fetch(self, *remotes: str) -> None:
        pass

    def create_branch(self, name: str, base: str) -> None:
        self._branches.append(name)
        self._current_branch = name

    def checkout(self, name: str) -> None:
        self._current_branch = name

    def owner(self, remote: str) -> str:
        return "bot"

    def last_commit_message(self, branch: str) -> str:
        return self._log[-1] if self._log else ""

    def reset(self, branch: str) -> None:
        pass

    def add(self, *files: str) -> None:
        pass

    def commit(self, msg: str, body: str) -> None:
        self._log.append(msg)

    def push(self, remote: str, branch: str, force: bool = False) -> None:
        pass

    def tag(self, tag: str, message: str, sign: bool) -> None:
        self._tags.append(tag)

    def verify_tag(self, tag: str) -> bool:
        return True

    def pull(self, remote: str) -> None:
        pass

    def remote_slug(self, remote: str) -> types.RepoSlug:
        return types.RepoSlug("TokTok", "ci-tools")


class TestReleaseE2E(unittest.TestCase):
    def test_full_release_lifecycle(self) -> None:
        config = Config(
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

        gh = FakeGitHub()
        gh._issues[1] = github.Issue(
            title="Release tracking issue",
            body="### Release notes\nCool notes\nProduction release",
            user="human",
            assignees=["toktok-releaser"],
            number=1,
            html_url="url",
            state="open",
            milestone=1,
        )

        # Setup simulated CI pass
        gh._checks["sha123"] = {
            "test": github.CheckRun(
                id=1,
                name="test",
                status="completed",
                conclusion="success",
                html_url="url",
            )
        }
        gh._action_runs["sha123"] = [
            github.ActionRun(
                id=1,
                node_id="node",
                name="ci",
                status="completed",
                event="push",
                conclusion="success",
                html_url="url",
                path=".github/workflows/ci.yml",
            )
        ]

        gt = FakeGit()

        releaser = Releaser(config, gt, gh)

        m_open = mock_open(read_data="/ci-tools\n")

        # We need to simulate progress through stages.
        call_counts = {"get_head_pr": 0, "action_runs": 0}

        original_get_head_pr = releaser.get_head_pr

        def mock_get_head_pr(version: str) -> github.PullRequest | None:
            pr = original_get_head_pr(version)
            if pr:
                call_counts["get_head_pr"] += 1
                # After 2 calls in 'Await merged', simulate merge
                if call_counts["get_head_pr"] > 2:
                    pr.state = "closed"
                    pr.merged = True
            return pr

        setattr(releaser, "get_head_pr", mock_get_head_pr)

        def mock_action_runs(branch: str, sha: str) -> list[github.ActionRun]:
            call_counts["action_runs"] += 1
            # For Await master build, return completed runs after some time
            return (
                [
                    github.ActionRun(
                        id=1,
                        node_id="node",
                        name="ci",
                        status="completed",
                        event="push",
                        conclusion="success",
                        html_url="url",
                        path=".github/workflows/ci.yml",
                    )
                ]
                if call_counts["action_runs"] > 1
                else []
            )

        setattr(gh, "action_runs", mock_action_runs)

        with patch("lib.changelog.get_release_notes") as mock_get_notes, patch(
            "lib.changelog.has_release_notes", return_value=True
        ), patch("lib.changelog.set_release_notes"), patch(
            "os.path.exists", return_value=True
        ), patch(
            "subprocess.run"
        ), patch(
            "builtins.open", m_open
        ), patch(
            "validate_pr.main"
        ), patch(
            "lib.stage.sleep"
        ), patch(
            "create_tarballs.main"
        ), patch(
            "sign_release_assets.main"
        ), patch(
            "verify_release_assets.main"
        ), patch(
            "lib.github.DEFAULT_GITHUB", gh
        ), patch(
            "lib.git.DEFAULT_GIT", gt
        ):

            mock_get_notes.return_value = MagicMock(notes="Cool notes")
            mock_get_notes.return_value.formatted.return_value = "Formatted notes"

            try:
                releaser.run_stages()
            except stage.UserAbort:
                pass

            # Verify intermediate dashboard state during UserAbort for publishing
            self.assertIn("**Current Step: Finalize release**", gh._issues[1].body)
            self.assertIn(
                "Action Required:** All checks passed and assets signed",
                gh._issues[1].body,
            )

            # Simulate user published release and re-run
            gh._release_published = True
            releaser.run_stages()

        self.assertIn("release/v1.0.0", gt._branches)
        self.assertIn("v1.0.0", gt._tags)
        self.assertEqual(gh._issues[1].state, "closed")
        self.assertIn("[x] Finalize release", gh._issues[1].body)

    def test_release_ci_failure(self) -> None:
        config = Config(
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

        gh = FakeGitHub()
        gh._issues[1] = github.Issue(
            title="Release tracking issue",
            body="### Release notes\nCool notes\nProduction release",
            user="human",
            assignees=["toktok-releaser"],
            number=1,
            html_url="url",
            state="open",
            milestone=1,
        )

        # Setup simulated CI failure
        gh._checks["sha123"] = {
            "test": github.CheckRun(
                id=1,
                name="test",
                status="completed",
                conclusion="failure",
                html_url="url",
            )
        }

        gt = FakeGit()
        releaser = Releaser(config, gt, gh)
        m_open = mock_open(read_data="/ci-tools\n")

        with patch("lib.changelog.get_release_notes") as mock_get_notes, patch(
            "lib.changelog.has_release_notes", return_value=True
        ), patch("lib.changelog.set_release_notes"), patch(
            "os.path.exists", return_value=True
        ), patch(
            "subprocess.run"
        ), patch(
            "builtins.open", m_open
        ), patch(
            "validate_pr.main"
        ), patch(
            "lib.stage.sleep"
        ), patch(
            "lib.github.DEFAULT_GITHUB", gh
        ), patch(
            "lib.git.DEFAULT_GIT", gt
        ):

            mock_get_notes.return_value = MagicMock(notes="Cool notes")

            with self.assertRaises(stage.InvalidState) as cm:
                releaser.run_stages()

            self.assertIn("checks failed", str(cm.exception))

    def test_release_ci_timeout(self) -> None:
        config = Config(
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

        gh = FakeGitHub()
        gh._issues[1] = github.Issue(
            title="Release tracking issue",
            body="### Release notes\nCool notes\nProduction release",
            user="human",
            assignees=["toktok-releaser"],
            number=1,
            html_url="url",
            state="open",
            milestone=1,
        )

        # Setup simulated CI hanging
        gh._checks["sha123"] = {
            "test": github.CheckRun(
                id=1, name="test", status="in_progress", conclusion="", html_url="url"
            )
        }

        gt = FakeGit()
        releaser = Releaser(config, gt, gh)
        m_open = mock_open(read_data="/ci-tools\n")

        with patch("lib.changelog.get_release_notes") as mock_get_notes, patch(
            "lib.changelog.has_release_notes", return_value=True
        ), patch("lib.changelog.set_release_notes"), patch(
            "os.path.exists", return_value=True
        ), patch(
            "subprocess.run"
        ), patch(
            "builtins.open", m_open
        ), patch(
            "validate_pr.main"
        ), patch(
            "lib.stage.sleep"
        ), patch(
            "lib.github.DEFAULT_GITHUB", gh
        ), patch(
            "lib.git.DEFAULT_GIT", gt
        ):

            mock_get_notes.return_value = MagicMock(notes="Cool notes")

            with self.assertRaises(stage.InvalidState) as cm:
                releaser.run_stages()

            self.assertIn("Timeout waiting for checks to pass", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
