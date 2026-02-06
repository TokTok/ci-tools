#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2026 The TokTok team
import contextlib
import unittest
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

from create_release import Config, Releaser
from lib import git, github, stage, types


class FakeGitHub(github.GitHub):
    def __init__(self) -> None:
        super().__init__(
            api_url="https://api.github.com",
            github_token="fake_github_token",  # nosec
            releaser_token="fake_releaser_token",  # nosec
        )
        self._issues: dict[int, dict[str, Any]] = {}
        self._prs: list[dict[str, Any]] = []
        self._milestones: list[dict[str, Any]] = []
        self._assets: dict[int, list[dict[str, Any]]] = {}
        self._releases: list[dict[str, Any]] = []
        self._checks: dict[str, dict[str, github.CheckRun]] = {}
        self._action_runs: dict[str, list[github.ActionRun]] = {}
        self._user = {"login": "human"}

    def _auth_headers(self, auth: github.AuthLevel) -> dict[str, str]:
        return {"Authorization": "Token fake"}  # nosec

    def api(
        self,
        url: str,
        auth: github.AuthLevel = github.AuthLevel.OPTIONAL,
        params: tuple[tuple[str, str | int], ...] = tuple(),
    ) -> Any:
        if url == "/user":
            return self._user
        if url.endswith("/releases"):
            return self._releases
        if url.endswith("/milestones"):
            return self._milestones
        if url.endswith("/issues"):
            params_dict = dict(params)
            milestone = params_dict.get("milestone")
            return [
                i
                for i in self._issues.values()
                if milestone is None
                or (
                    isinstance(i["milestone"], dict)
                    and i["milestone"]["number"] == int(milestone)
                )
                or (
                    isinstance(i["milestone"], int) and i["milestone"] == int(milestone)
                )
            ]
        if "/issues/" in url:
            issue_id = int(url.split("/")[-1])
            return self._issues[issue_id]
        if url.endswith("/pulls"):
            return self._prs
        if "/releases/" in url:
            rid_str = url.split("/")[-1]
            if rid_str == "latest":
                return self._releases[-1] if self._releases else None
            try:
                rid = int(rid_str)
                for r in self._releases:
                    if r["id"] == rid:
                        # Return a copy and add assets
                        r_copy = r.copy()
                        r_copy["assets"] = self._assets.get(rid, [])
                        return r_copy
            except ValueError:
                pass
        if "/branches/" in url:
            return {"name": url.split("/")[-1]}
        raise ValueError(f"URL not mocked in FakeGitHub: {url}")

    def api_uncached(
        self,
        url: str,
        auth: github.AuthLevel = github.AuthLevel.OPTIONAL,
        params: tuple[tuple[str, str | int], ...] = tuple(),
    ) -> Any:
        return self.api(url, auth, params)

    def api_post(
        self,
        url: str,
        auth: github.AuthLevel = github.AuthLevel.GITHUB,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if url.endswith("/pulls"):
            pr = {
                "title": json["title"],
                "body": json["body"],
                "number": 123 + len(self._prs),
                "user": {"login": "toktok-releaser"},
                "assignees": [],
                "node_id": f"node{len(self._prs)}",
                "html_url": f"url{len(self._prs)}",
                "state": "open",
                "head": {"sha": "sha123", "ref": json["head"]},
                "milestone": None,
                "draft": json.get("draft", False),
                "merged_at": None,
            }
            self._prs.append(pr)
            self._issues[pr["number"]] = pr
            return pr
        if url.endswith("/releases"):
            for r in self._releases:
                if r["tag_name"] == json["tag_name"]:
                    return r
            release = {
                "id": len(self._releases) + 1,
                "tag_name": json["tag_name"],
                "body": json["body"],
                "prerelease": json["prerelease"],
                "draft": json["draft"],
                "published_at": None,
            }
            self._releases.append(release)
            return release
        if url.endswith("/assignees"):
            issue_id = int(url.split("/")[-2])
            self._issues[issue_id]["assignees"].extend(
                [{"login": a} for a in json["assignees"]]
            )
            return None
        if "/git/tags" in url:
            return {"sha": "sha_tag"}
        if "/git/refs" in url:
            return None
        if "/git/blobs" in url:
            return {"sha": "sha_blob"}
        if "/git/trees" in url:
            return {"sha": "sha_tree"}
        if "/git/commits" in url:
            return {"sha": "sha_commit"}
        raise ValueError(f"POST URL not mocked in FakeGitHub: {url}")

    def api_post_uploads(
        self,
        url: str,
        content_type: str,
        data: Any,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return None

    def api_patch(
        self,
        url: str,
        auth: github.AuthLevel = github.AuthLevel.GITHUB,
        json: Any = None,
    ) -> Any:
        if "/issues/" in url:
            issue_id = int(url.split("/")[-1])
            if json and "milestone" in json and isinstance(json["milestone"], int):
                json = json.copy()
                json["milestone"] = {"number": json["milestone"]}
            self._issues[issue_id].update(json)
            return self._issues[issue_id]
        if "/pulls/" in url:
            pr_id = int(url.split("/")[-1])
            for pr in self._prs:
                if pr["number"] == pr_id:
                    pr.update(json)
                    return pr
            return None
        if "/milestones/" in url:
            return None
        if "/releases/" in url:
            rid = int(url.split("/")[-1])
            for r in self._releases:
                if r["id"] == rid:
                    r.update(json)
                    return r
            return None
        if "/git/refs/" in url:
            return None
        raise ValueError(f"PATCH URL not mocked in FakeGitHub: {url}")

    def api_delete(
        self,
        url: str,
        auth: github.AuthLevel = github.AuthLevel.GITHUB,
        json: Any = None,
    ) -> None:
        if url.endswith("/assignees"):
            issue_id = int(url.split("/")[-2])
            assignees_to_remove = set(json["assignees"])
            self._issues[issue_id]["assignees"] = [
                a
                for a in self._issues[issue_id]["assignees"]
                if a["login"] not in assignees_to_remove
            ]
            return
        raise ValueError(f"DELETE URL not mocked in FakeGitHub: {url}")

    def actor(self) -> str:
        return "human"

    def repository(self) -> str:
        return "TokTok/ci-tools"

    def repository_name(self) -> str:
        return "ci-tools"

    def find_pr_for_branch(
        self, head: str, base: str, state: str = "all"
    ) -> github.PullRequest | None:
        for pr_data in self._prs:
            if pr_data["state"] == state or state == "all":
                if pr_data["head"]["ref"] == head.split(":")[-1]:
                    return github.PullRequest.fromJSON(pr_data)
        return None

    def find_pr(self, head_sha: str, base: str) -> github.PullRequest | None:
        for pr_data in self._prs:
            if pr_data["head"]["sha"] == head_sha:
                return github.PullRequest.fromJSON(pr_data)
        return None

    def action_runs(self, branch: str, head_sha: str) -> list[github.ActionRun]:
        return self._action_runs.get(head_sha, [])

    def checks(self, commit: str) -> dict[str, github.CheckRun]:
        return self._checks.get(commit, {})

    def graphql(self, query: str) -> Any:
        return {"data": {}}

    def clear_cache(self) -> None:
        pass

    def add_issue(
        self,
        number: int,
        title: str,
        body: str,
        assignee: str = "toktok-releaser",
        milestone: int | None = None,
    ) -> None:
        self._issues[number] = {
            "title": title,
            "body": body,
            "user": {"login": "human"},
            "assignees": [{"login": assignee}],
            "number": number,
            "html_url": f"https://github.com/TokTok/ci-tools/issues/{number}",
            "state": "open",
            "milestone": {"number": milestone} if milestone else None,
        }

    def add_milestone(self, number: int, title: str) -> None:
        self._milestones.append(
            {
                "title": title,
                "number": number,
                "html_url": f"https://github.com/TokTok/ci-tools/milestone/{number}",
            }
        )


class FakeGit(git.Git):
    def __init__(self) -> None:
        self._branches: list[str] = ["master"]
        self._current_branch: str = "master"
        self._tags: list[str] = []
        self._log: list[str] = ["initial commit"]
        self._up_to_date = False
        self._rebase_success = True

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

    def root(self) -> str:
        return "/src/workspace/ci_tools"

    def remote_slug(self, remote: str) -> types.RepoSlug:
        return types.RepoSlug("TokTok", "ci-tools")

    def is_up_to_date(self, branch: str, upstream: str) -> bool:
        return self._up_to_date

    def rebase(self, branch: str, commits: int = 1) -> bool:
        return self._rebase_success


class TestReleaseE2E(unittest.TestCase):
    def make_config(self, **kwargs: Any) -> Config:
        defaults = {
            "branch": "master",
            "main_branch": "master",
            "dryrun": False,
            "force": True,
            "github_actions": True,
            "issue": 1,
            "production": True,
            "rebase": True,
            "resume": False,
            "verify": False,
            "version": "",
            "upstream": "origin",
        }
        defaults.update(kwargs)
        return Config(**defaults)

    def release_mocks(
        self, gh: FakeGitHub, gt: FakeGit, notes: str = "Cool notes"
    ) -> contextlib.ExitStack:
        m_open = mock_open(read_data="/ci-tools\n")
        stack = contextlib.ExitStack()
        stack.enter_context(
            patch.multiple(
                "lib.changelog",
                get_release_notes=MagicMock(
                    return_value=MagicMock(
                        notes=notes,
                        formatted=MagicMock(return_value=f"Formatted {notes}"),
                    )
                ),
                has_release_notes=MagicMock(return_value=True),
                set_release_notes=MagicMock(),
            )
        )
        stack.enter_context(patch("os.path.exists", return_value=True))
        stack.enter_context(patch("subprocess.run"))
        stack.enter_context(patch("builtins.open", m_open))
        stack.enter_context(patch("validate_pr.main"))
        stack.enter_context(patch("lib.stage.sleep"))
        stack.enter_context(patch("create_tarballs.main"))
        stack.enter_context(patch("sign_release_assets.main"))
        stack.enter_context(patch("verify_release_assets.main"))
        stack.enter_context(patch("lib.github.DEFAULT_GITHUB", gh))
        stack.enter_context(patch("lib.git.DEFAULT_GIT", gt))
        return stack

    def test_full_release_lifecycle(self) -> None:
        config = self.make_config()
        gh = FakeGitHub()
        gh.add_issue(
            1, "Release tracking issue", "### Release notes\nCool notes\nProduction release"
        )
        gh.add_milestone(1, "v1.0.0")
        gh._releases.append(
            {
                "id": 1,
                "tag_name": "v1.0.0",
                "published_at": None,
                "body": "Existing draft notes",
            }
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

        # We need to simulate progress through stages.
        call_counts = {"get_head_pr": 0, "action_runs": 0}
        original_get_head_pr = releaser.get_head_pr

        def mock_get_head_pr(version: str) -> github.PullRequest | None:
            pr = original_get_head_pr(version)
            if pr:
                call_counts["get_head_pr"] += 1
                if call_counts["get_head_pr"] > 2:
                    pr.state = "closed"
                    pr.merged = True
            return pr

        setattr(releaser, "get_head_pr", mock_get_head_pr)

        def mock_action_runs(branch: str, sha: str) -> list[github.ActionRun]:
            call_counts["action_runs"] += 1
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

        with self.release_mocks(gh, gt):
            try:
                releaser.run_stages()
            except stage.UserAbort:
                pass

            # Verify intermediate dashboard state
            self.assertIn("**Current Step: Finalize release**", gh._issues[1]["body"])
            self.assertIn(
                "Action Required:** All checks passed and assets signed",
                gh._issues[1]["body"],
            )

            # Simulate user published release, re-assign bot, and re-run
            gh._releases[0]["published_at"] = "2026-02-06T00:00:00Z"
            gh._issues[1]["assignees"] = [{"login": "toktok-releaser"}]
            releaser.run_stages()

        self.assertIn("release/v1.0.0", gt._branches)
        self.assertIn("v1.0.0", gt._tags)
        self.assertEqual(gh._issues[1]["state"], "closed")
        self.assertIn("[x] Finalize release", gh._issues[1]["body"])

    def test_invalid_issue_title(self) -> None:
        config = self.make_config()
        gh = FakeGitHub()
        gh.add_issue(1, "Not a release issue", "Some body")
        gt = FakeGit()
        releaser = Releaser(config, gt, gh)
        with patch("lib.github.DEFAULT_GITHUB", gh), patch("lib.git.DEFAULT_GIT", gt):
            with self.assertRaises(stage.UserAbort) as cm:
                releaser.run_stages()
            self.assertIn("deal with the issue", str(cm.exception))

    def test_prerelease_lifecycle(self) -> None:
        config = self.make_config(production=False)
        gh = FakeGitHub()
        gh.add_issue(
            1, "Release tracking issue", "### Release notes\nCool notes", milestone=1
        )
        gh.add_milestone(1, "v1.0.0")
        gh._releases.append(
            {
                "id": 1,
                "tag_name": "v1.0.0-rc.1",
                "published_at": "2026-02-06T00:00:00Z",
                "prerelease": True,
                "draft": False,
            }
        )

        gt = FakeGit()
        releaser = Releaser(config, gt, gh)

        with self.release_mocks(gh, gt):
            gh._checks["sha123"] = {
                "test": github.CheckRun(1, "test", "completed", "success", "url")
            }
            gh._action_runs["sha123"] = [
                github.ActionRun(
                    1, "node", "ci", "completed", "push", "success", "url", "path"
                )
            ]

            original_get_head_pr = releaser.get_head_pr

            def mock_get_head_pr(version: str) -> github.PullRequest | None:
                pr = original_get_head_pr(version)
                if pr:
                    pr.state = "closed"
                    pr.merged = True
                return pr

            setattr(releaser, "get_head_pr", mock_get_head_pr)

            try:
                releaser.run_stages()
            except stage.UserAbort:
                pass

            self.assertIn("v1.0.0-rc.2", gt._tags)
            self.assertEqual(
                len([m for m in gh._milestones if m.get("state") == "closed"]), 0
            )

    def test_existing_pr_update(self) -> None:
        config = self.make_config(version="v1.0.0")
        gh = FakeGitHub()
        gh._prs.append(
            {
                "title": "chore: Release v1.0.0",
                "body": "<!-- Releaser:start -->\nOld notes\n<!-- Releaser:end -->\n",
                "number": 555,
                "user": {"login": "toktok-releaser"},
                "assignees": [],
                "node_id": "node555",
                "html_url": "url555",
                "state": "open",
                "head": {"sha": "sha123", "ref": "release/v1.0.0"},
                "milestone": {"number": 1},
                "draft": True,
                "merged_at": None,
            }
        )
        gh._issues[555] = gh._prs[0]
        gh.add_issue(
            1,
            "Release tracking issue: v1.0.0",
            "### Release notes\nNew notes\nProduction release",
            milestone=1,
        )
        gh.add_milestone(1, "v1.0.0")

        gt = FakeGit()
        gt._branches.append("release/v1.0.0")

        releaser = Releaser(config, gt, gh)
        with self.release_mocks(gh, gt, notes="New notes"):
            releaser.stage_pull_request("v1.0.0")
            self.assertIn("New notes", gh._prs[0]["body"])

    def test_branch_exists_reset(self) -> None:
        config = self.make_config(version="v1.0.0")
        gh = FakeGitHub()
        gt = FakeGit()
        gt._branches.append("release/v1.0.0")
        gt._log.append("some other commit")

        releaser = Releaser(config, gt, gh)
        with patch("lib.github.DEFAULT_GITHUB", gh), patch("lib.git.DEFAULT_GIT", gt):
            releaser.stage_branch("v1.0.0")
            self.assertEqual(gt.current_branch(), "release/v1.0.0")

    def test_tag_exists_but_release_missing(self) -> None:
        config = self.make_config(version="v1.0.0")
        gh = FakeGitHub()
        gt = FakeGit()
        gt._tags.append("v1.0.0")

        releaser = Releaser(config, gt, gh)
        with self.release_mocks(gh, gt):
            releaser.stage_tag("v1.0.0")
            self.assertEqual(len(gh._releases), 1)
            self.assertEqual(gh._releases[0]["tag_name"], "v1.0.0")

    def test_dryrun_lifecycle(self) -> None:
        config = self.make_config(dryrun=True)
        gh = FakeGitHub()
        gh.add_issue(
            1, "Release tracking issue", "### Release notes\nCool notes\nProduction release"
        )
        gh.add_milestone(1, "v1.0.0")
        gt = FakeGit()
        releaser = Releaser(config, gt, gh)

        with self.release_mocks(gh, gt):
            releaser.run_stages()

            # Dry run should not push tags
            self.assertEqual(len(gt._tags), 0)
            # Dry run should not create releases
            self.assertEqual(len(gh._releases), 0)

    def test_release_ci_failure(self) -> None:
        config = self.make_config()
        gh = FakeGitHub()
        gh.add_issue(
            1, "Release tracking issue", "### Release notes\nCool notes\nProduction release"
        )
        gh.add_milestone(1, "v1.0.0")
        gh._releases.append(
            {
                "id": 1,
                "tag_name": "v1.0.0",
                "published_at": None,
                "body": "Existing draft notes",
            }
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

        with self.release_mocks(gh, gt):
            with self.assertRaises(stage.InvalidState) as cm:
                releaser.run_stages()

            self.assertIn("checks failed", str(cm.exception))

    def test_release_ci_timeout(self) -> None:
        config = self.make_config()
        gh = FakeGitHub()
        gh.add_issue(
            1, "Release tracking issue", "### Release notes\nCool notes\nProduction release"
        )
        gh.add_milestone(1, "v1.0.0")
        gh._releases.append(
            {
                "id": 1,
                "tag_name": "v1.0.0",
                "published_at": None,
                "body": "Existing draft notes",
            }
        )

        # Setup simulated CI hanging
        gh._checks["sha123"] = {
            "test": github.CheckRun(
                id=1, name="test", status="in_progress", conclusion="", html_url="url"
            )
        }

        gt = FakeGit()
        releaser = Releaser(config, gt, gh)

        with self.release_mocks(gh, gt):
            with self.assertRaises(stage.InvalidState) as cm:
                releaser.run_stages()

            self.assertIn("Timeout waiting for checks to pass", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
