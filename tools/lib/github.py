#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2026 The TokTok team
import os
import re
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from typing import IO, Any

import requests
from lib import git, types


class AuthLevel(Enum):
    OPTIONAL = 0
    GITHUB = 1
    RELEASER = 2


@dataclass
class Milestone:
    title: str
    number: int
    html_url: str

    @staticmethod
    def fromJSON(m: dict[str, Any]) -> "Milestone":
        return Milestone(
            title=str(m["title"]),
            number=int(m["number"]),
            html_url=str(m["html_url"]),
        )


@dataclass
class Issue:
    title: str
    body: str
    user: str
    assignees: list[str]
    number: int
    html_url: str
    state: str
    milestone: int | None

    @staticmethod
    def fromJSON(issue: dict[str, Any]) -> "Issue":
        return Issue(
            title=str(issue["title"]),
            body=str(issue["body"]),
            user=str(issue["user"]["login"]),
            assignees=[str(a["login"]) for a in issue["assignees"]],
            number=int(issue["number"]),
            html_url=str(issue["html_url"]),
            state=str(issue["state"]),
            milestone=int(issue["milestone"]["number"]) if issue["milestone"] else None,
        )


@dataclass
class PullRequest:
    title: str
    body: str
    number: int
    node_id: str
    html_url: str
    state: str
    head_sha: str
    milestone: int | None
    draft: bool
    merged: bool

    @staticmethod
    def fromJSON(pr: dict[str, Any]) -> "PullRequest":
        return PullRequest(
            title=str(pr["title"]),
            body=str(pr["body"]),
            number=int(pr["number"]),
            node_id=str(pr["node_id"]),
            html_url=str(pr["html_url"]),
            state=str(pr["state"]),
            head_sha=str(pr["head"]["sha"]),
            milestone=int(pr["milestone"]["number"]) if pr["milestone"] else None,
            draft=bool(pr["draft"]),
            merged=pr["merged_at"] is not None,
        )


@dataclass
class CheckRun:
    id: int
    name: str
    status: str
    conclusion: str
    html_url: str

    @staticmethod
    def fromJSON(run: dict[str, Any]) -> "CheckRun":
        return CheckRun(
            id=int(run["id"]),
            name=str(run["name"]),
            status=str(run["status"]),
            conclusion=str(run["conclusion"]),
            html_url=str(run["html_url"]),
        )


@dataclass
class ActionRun:
    id: int
    node_id: str
    name: str
    status: str
    event: str
    conclusion: str
    html_url: str
    path: str

    @staticmethod
    def fromJSON(run: dict[str, Any]) -> "ActionRun":
        return ActionRun(
            id=int(run["id"]),
            node_id=str(run["node_id"]),
            name=str(run["name"]),
            status=str(run["status"]),
            event=str(run["event"]),
            conclusion=str(run["conclusion"]),
            html_url=str(run["html_url"]),
            path=str(run["path"]),
        )


@dataclass
class ReleaseAsset:
    id: int
    name: str
    content_type: str
    url: str
    browser_download_url: str

    @staticmethod
    def fromJSON(asset: dict[str, Any]) -> "ReleaseAsset":
        return ReleaseAsset(
            id=int(asset["id"]),
            name=str(asset["name"]),
            content_type=str(asset["content_type"]),
            url=str(asset["url"]),
            browser_download_url=str(asset["browser_download_url"]),
        )


def _process_error(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(response.json())
        raise e


api_requests: list[str] = []


class GitHub:
    """A provider for GitHub API calls."""

    def __init__(
        self,
        git_prov: git.Git = git.DEFAULT_GIT,
        api_url: str = os.getenv("GITHUB_API_URL") or "https://api.github.com",
        github_token: str | None = os.getenv("GITHUB_TOKEN"),
        releaser_token: str | None = os.getenv("TOKEN_RELEASES"),
        repo_name: str | None = os.getenv("GITHUB_REPOSITORY"),
    ) -> None:
        self.git = git_prov
        self._api_url = api_url
        self._github_token = github_token
        self._releaser_token = releaser_token
        self._repo_name = repo_name
        self._cache: dict[tuple[Any, ...], Any] = {}

        if self._github_token:
            print("Authorization with GITHUB_TOKEN")
        else:
            print("Unauthorized (low rate limit applies)")
            print("Set GITHUB_TOKEN to increase the rate limit")

        if self._releaser_token:
            print("Authorization with TOKEN_RELEASES")

    def _process_error(self, response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(response.json())
            raise e

    def _auth_headers(self, auth: AuthLevel) -> dict[str, str]:
        token = (
            self._releaser_token if auth == AuthLevel.RELEASER else self._github_token
        )
        if not token:
            if auth != AuthLevel.OPTIONAL:
                raise ValueError("GITHUB_TOKEN is needed")
            return {}
        return {"Authorization": f"Token {token}"}

    def api_uncached(
        self,
        url: str,
        auth: AuthLevel = AuthLevel.OPTIONAL,
        params: tuple[tuple[str, str | int], ...] = tuple(),
    ) -> Any:
        api_requests.append(f"GET {self._api_url}{url}")
        response = requests.get(
            f"{self._api_url}{url}",
            headers=self._auth_headers(auth=auth),
            params=dict(params),
        )
        self._process_error(response)
        return response.json()

    def api_post(
        self,
        url: str,
        auth: AuthLevel = AuthLevel.GITHUB,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        api_requests.append(f"POST {self._api_url}{url}")
        response = requests.post(
            f"{self._api_url}{url}",
            headers=self._auth_headers(auth=auth),
            json=json,
            params=params,
        )
        self._process_error(response)
        if response.content:
            return response.json()
        return None

    def api_patch(
        self,
        url: str,
        auth: AuthLevel = AuthLevel.GITHUB,
        json: Any = None,
    ) -> Any:
        api_requests.append(f"PATCH {self._api_url}{url}")
        response = requests.patch(
            f"{self._api_url}{url}",
            headers=self._auth_headers(auth=auth),
            json=json,
        )
        self._process_error(response)
        if response.content:
            return response.json()
        return None

    def api_put(
        self,
        url: str,
        auth: AuthLevel = AuthLevel.GITHUB,
        json: Any = None,
    ) -> Any:
        api_requests.append(f"PUT {self._api_url}{url}")
        response = requests.put(
            f"{self._api_url}{url}",
            headers=self._auth_headers(auth=auth),
            json=json,
        )
        self._process_error(response)
        if response.content:
            return response.json()
        return None

    def api_delete(
        self,
        url: str,
        auth: AuthLevel = AuthLevel.GITHUB,
        json: Any = None,
    ) -> None:
        api_requests.append(f"DELETE {self._api_url}{url}")
        response = requests.delete(
            f"{self._api_url}{url}",
            headers=self._auth_headers(auth=auth),
            json=json,
        )
        self._process_error(response)

    def api(
        self,
        url: str,
        auth: AuthLevel = AuthLevel.OPTIONAL,
        params: tuple[tuple[str, str | int], ...] = tuple(),
    ) -> Any:
        key = (url, auth, params)
        if key not in self._cache:
            self._cache[key] = self.api_uncached(url, auth, params)
        return self._cache[key]

    def clear_cache(self) -> None:
        """Clear the cache of API calls."""
        self._cache.clear()

    def graphql(self, query: str) -> Any:
        """Call the GitHub GraphQL API with the given query."""
        response = requests.post(
            f"{self._api_url}/graphql",
            headers={
                "Accept": "application/json",
                **self._auth_headers(AuthLevel.GITHUB),
            },
            json={"query": query},
        )
        self._process_error(response)
        return response.json()["data"]

    def username(self) -> str | None:
        """Get the GitHub username for the current authenticated user."""
        if not self._github_token:
            return None
        return str(self.api("/user", auth=AuthLevel.GITHUB)["login"])

    def get_release_id(self, tag: str) -> int | None:
        """Get the GitHub release ID number for a tag, or None if not found."""
        for release in self.api(f"/repos/{self.repository()}/releases"):
            if release["tag_name"] == tag:
                return int(release["id"])
        return None

    def release_id(self, tag: str) -> int:
        """Get the GitHub release ID number for a tag."""
        rid = self.get_release_id(tag)
        if rid is not None:
            return rid
        raise ValueError(f"Release {tag} not found in {self.repository()}")

    def get_release(self, tag: str) -> Any:
        """Get the full release object for a tag, or None if not found."""
        rid = self.get_release_id(tag)
        if rid is None:
            return None
        return self.api_uncached(f"/repos/{self.repository()}/releases/{rid}")

    def release(self, tag: str) -> Any:
        """Get the full release object for a tag."""
        release = self.get_release(tag)
        if release is not None:
            return release
        raise ValueError(f"Release {tag} not found in {self.repository()}")

    def actor(self) -> str:
        """Returns the GitHub username for the current repository."""
        github_actor = os.getenv("GITHUB_ACTOR")
        if github_actor:
            return github_actor
        u = self.username()
        if u:
            return u
        remotes = self.git.remotes()
        for remote in ("origin", "upstream"):
            if remote in remotes:
                try:
                    slug = self.git.remote_slug(remote)
                    return slug.owner
                except ValueError:
                    continue
        raise ValueError("Could not determine GitHub actor")

    def repository(self) -> str:
        if self._repo_name:
            return self._repo_name
        github_repository = os.getenv("GITHUB_REPOSITORY")
        if github_repository:
            return github_repository
        remotes = self.git.remotes()
        for remote in ("upstream", "origin"):
            if remote in remotes:
                try:
                    slug = self.git.remote_slug(remote)
                    return str(slug)
                except ValueError:
                    continue
        raise ValueError("Could not determine repository")

    def repository_name(self) -> str:
        try:
            return self.repository().split("/")[-1]
        except ValueError:
            return os.path.basename(self.git.root())

    def milestones(self) -> dict[str, Milestone]:
        """Get the names and IDs of all milestones in the repository."""
        return {
            m["title"]: Milestone.fromJSON(m)
            for m in self.api(f"/repos/{self.repository()}/milestones")
        }

    def milestone(self, title: str) -> Milestone:
        """Get the milestone with the given title."""
        return self.milestones()[title]

    def next_milestone(self) -> Milestone:
        """Get the next release number (based on the smallest open milestone)."""
        return min(
            (
                m
                for m in self.milestones().values()
                if re.match(r"v\d+\.\d+\.\d+$", m.title)
            ),
            key=lambda m: tuple(map(int, m.title[1:].split("."))),
        )

    def assign_milestone(self, issue_id: int, milestone: int) -> None:
        """Assign the given milestone to the given issue."""
        self.api_patch(
            f"/repos/{self.repository()}/issues/{issue_id}",
            json={"milestone": milestone},
        )

    def close_milestone(self, number: int) -> None:
        """Close the milestone with the given number."""
        self.api_patch(
            f"/repos/{self.repository()}/milestones/{number}",
            json={"state": "closed"},
        )

    def open_milestone_issues(self, milestone: int) -> list[Issue]:
        """Get all the open issues for a given milestone."""
        return [
            Issue.fromJSON(i)
            for i in self.api(
                f"/repos/{self.repository()}/issues",
                params=(
                    ("milestone", milestone),
                    ("state", "open"),
                ),
            )
        ]

    def get_issue(self, issue_number: int) -> Issue:
        """Get the issue with the given number."""
        return Issue.fromJSON(
            self.api(f"/repos/{self.repository()}/issues/{issue_number}")
        )

    def rename_issue(self, issue_number: int, title: str) -> None:
        """Rename the issue with the given number."""
        self.api_patch(
            f"/repos/{self.repository()}/issues/{issue_number}",
            json={"title": title},
        )

    def close_issue(self, issue_number: int) -> None:
        """Close the issue with the given number."""
        self.api_patch(
            f"/repos/{self.repository()}/issues/{issue_number}",
            json={"state": "closed"},
        )

    def latest_release(self) -> str:
        """Get the name of the current release in the repository."""
        return str(self.api(f"/repos/{self.repository()}/releases/latest")["tag_name"])

    def prereleases(self, version: str) -> list[str]:
        """Get the names of all prereleases for a given version in the repository."""
        return [
            r["tag_name"]
            for r in self.api(f"/repos/{self.repository()}/releases")
            if f"{version}-rc." in r["tag_name"] and r["prerelease"] and not r["draft"]
        ]

    def release_candidates(self, version: str) -> list[int]:
        """Get the RC numbers for prereleases of a given version."""
        return [
            int(i)
            for r in self.prereleases(version)
            for i in re.findall(r"-rc\.(\d+)$", r)
        ]

    def issue_assign(self, issue_id: int, assignees: list[str]) -> None:
        """Assign the given issue to the given list of users."""
        self.api_post(
            f"/repos/{self.repository()}/issues/{issue_id}/assignees",
            json={"assignees": assignees},
        )

    def issue_unassign(self, issue_id: int, assignees: list[str]) -> None:
        """Unassign the given issue from the given list of users."""
        self.api_delete(
            f"/repos/{self.repository()}/issues/{issue_id}/assignees",
            json={"assignees": assignees},
        )

    def create_pr(
        self, title: str, body: str, head: str, base: str, milestone: int
    ) -> PullRequest:
        """Create a pull request with the given title and body."""
        pr_json = self.api_post(
            f"/repos/{self.repository()}/pulls",
            auth=AuthLevel.RELEASER,
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
                "draft": True,
            },
        )
        pr = PullRequest.fromJSON(pr_json)
        if milestone:
            self.change_issue(pr.number, {"milestone": milestone})
        return pr

    def find_pr(self, head_sha: str, base: str) -> PullRequest | None:
        """Find a PR with the given title, head.sha, and base."""
        response = self.api_uncached(
            f"/repos/{self.repository()}/pulls",
            params=(
                ("state", "all"),
                ("base", base),
                ("per_page", 100),
            ),
        )
        for pr in response:
            if pr["head"]["sha"] == head_sha:
                return PullRequest.fromJSON(pr)
        return None

    def find_pr_for_branch(
        self, head: str, base: str, state: str = "all"
    ) -> PullRequest | None:
        """Find a PR with the given head (actor:branch) and base."""
        response = self.api_uncached(
            f"/repos/{self.repository()}/pulls",
            params=(
                ("state", state),
                ("base", base),
                ("head", head),
                ("per_page", 100),
            ),
        )
        return PullRequest.fromJSON(response[0]) if response else None

    def change_pr(self, number: int, changes: dict[str, str | int]) -> None:
        """Modify a PR with the given number."""
        self.api_patch(
            f"/repos/{self.repository()}/pulls/{number}",
            json=changes,
        )

    def change_issue(self, number: int, changes: dict[str, str | int]) -> None:
        """Modify an issue with the given number."""
        self.api_patch(
            f"/repos/{self.repository()}/issues/{number}",
            json=changes,
        )

    def checks(self, commit: str) -> dict[str, CheckRun]:
        """Return all the GitHub Actions results."""
        check_runs = {
            r["name"]: CheckRun.fromJSON(r)
            for s in self.api_uncached(
                f"/repos/{self.repository()}/commits/{commit}/check-suites",
            )["check_suites"]
            for r in self.api_uncached(
                f"/repos/{self.repository()}/check-suites/{s['id']}/check-runs",
            )["check_runs"]
        }
        return check_runs

    def action_runs(self, branch: str, head_sha: str) -> list[ActionRun]:
        """Return all the GitHub Actions results."""
        return [
            ActionRun.fromJSON(r)
            for r in self.api_uncached(
                f"/repos/{self.repository()}/actions/runs",
                params=(("branch", branch), ("head_sha", head_sha)),
            )["workflow_runs"]
        ]

    def download_artifact(self, name: str, run_id: int) -> bytes:
        """Download the artifact with the given name from the given run."""
        response = requests.get(
            f"{self._api_url}/repos/{self.repository()}/actions/runs/{run_id}/artifacts",
            headers=self._auth_headers(AuthLevel.GITHUB),
        )
        self._process_error(response)
        for artifact in response.json()["artifacts"]:
            if artifact["name"] == name:
                response = requests.get(
                    f"{self._api_url}/repos/{self.repository()}/actions/artifacts/{artifact['id']}/zip",
                    headers=self._auth_headers(AuthLevel.GITHUB),
                )
                self._process_error(response)
                return response.content
        raise ValueError(f"Artifact {name} not found in run {run_id}")

    def release_assets(self, tag: str) -> list[ReleaseAsset]:
        """Return all the assets for a given tag."""
        rid = self.get_release_id(tag)
        if rid is None:
            return []
        return [
            ReleaseAsset.fromJSON(a)
            for a in self.api_uncached(f"/repos/{self.repository()}/releases/{rid}")[
                "assets"
            ]
        ]

    def download_asset(self, asset_id: int) -> bytes:
        """Download the asset with the given ID."""
        response = requests.get(
            f"{self._api_url}/repos/{self.repository()}/releases/assets/{asset_id}",
            headers={
                "Accept": "application/octet-stream",
                **self._auth_headers(AuthLevel.OPTIONAL),
            },
        )
        self._process_error(response)
        return response.content

    def api_post_uploads(
        self,
        url: str,
        content_type: str,
        data: Any,
        params: dict[str, Any] | None = None,
    ) -> Any:
        api_requests.append(f"POST https://uploads.github.com{url}")
        response = requests.post(
            f"https://uploads.github.com{url}",
            headers={
                "Content-Type": content_type,
                **self._auth_headers(AuthLevel.GITHUB),
            },
            data=data,
            params=params,
        )
        self._process_error(response)
        if response.content:
            return response.json()
        return None

    def upload_asset(
        self, tag: str, filename: str, content_type: str, data: bytes | IO[bytes]
    ) -> None:
        """Upload an asset to the release with the given tag."""
        rid = self.release_id(tag)
        self.api_post_uploads(
            f"/repos/{self.repository()}/releases/{rid}/assets",
            content_type,
            data,
            params={"name": filename},
        )

    def mark_ready_for_review(self, pr_node_id: str) -> None:
        """Mark a PR as ready for review."""
        self.graphql(f"""
            mutation MarkPrReady {{
                markPullRequestReadyForReview(input: {{pullRequestId: "{pr_node_id}"}}) {{
                    pullRequest {{
                        id
                    }}
                }}
            }}
        """)

    def push_signed(
        self,
        slug: types.RepoSlug,
        commit_sha: str,
        head_branch: str,
        target_branch: str,
    ) -> str:
        """Create a signed commit (by github-actions[bot]) for the given commit."""
        files_changed = self.git.files_changed(commit_sha)
        tree_objects = []
        for file in files_changed:
            with open(file, "rb") as f:
                blob_response = self.api_post(
                    f"/repos/{slug}/git/blobs",
                    json={"content": f.read().decode("utf-8"), "encoding": "utf-8"},
                )
                tree_objects.append(
                    {
                        "path": file,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_response["sha"],
                    }
                )
        head_sha = self.git.branch_sha(head_branch)
        tree_response = self.api_post(
            f"/repos/{slug}/git/trees",
            json={
                "base_tree": head_sha,
                "tree": tree_objects,
            },
        )
        commit_response = self.api_post(
            f"/repos/{slug}/git/commits",
            json={
                "message": self.git.commit_message(commit_sha),
                "tree": tree_response["sha"],
                "parents": [head_sha],
            },
        )
        target_sha = str(commit_response["sha"])
        try:
            self.api_uncached(
                f"/repos/{slug}/branches/{target_branch}", auth=AuthLevel.GITHUB
            )
            branch_exists = True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                branch_exists = False
            else:
                raise e

        if not branch_exists:
            self.api_post(
                f"/repos/{slug}/git/refs",
                auth=AuthLevel.RELEASER,
                json={
                    "ref": f"refs/heads/{target_branch}",
                    "sha": target_sha,
                },
            )
        else:
            branch_encoded = urllib.parse.quote_plus(target_branch)
            self.api_patch(
                f"/repos/{slug}/git/refs/heads/{branch_encoded}",
                auth=AuthLevel.RELEASER,
                json={
                    "sha": target_sha,
                    "force": True,
                },
            )
        return target_sha

    def tag(
        self, slug: types.RepoSlug, commit_sha: str, tag_name: str, tag_message: str
    ) -> str:
        """Create an unsigned tag (by github-actions[bot]) for the given commit."""
        if not tag_message.endswith("\n"):
            tag_message += "\n"
        tag_response = self.api_post(
            f"/repos/{slug}/git/tags",
            json={
                "tag": tag_name,
                "message": tag_message,
                "object": commit_sha,
                "type": "commit",
                "tagger": {
                    "name": "github-actions[bot]",
                    "email": "41898282+github-actions[bot]@users.noreply.github.com",
                },
            },
        )
        self.api_post(
            f"/repos/{slug}/git/refs",
            json={
                "ref": f"refs/tags/{tag_name}",
                "sha": tag_response["sha"],
            },
        )
        return str(tag_response["sha"])

    def create_release(self, tag: str, notes: str, prerelease: bool) -> Any:
        """Create a new release on GitHub."""
        rid = self.get_release_id(tag)
        if rid:
            return self.api_uncached(f"/repos/{self.repository()}/releases/{rid}")

        return self.api_post(
            f"/repos/{self.repository()}/releases",
            json={
                "tag_name": tag,
                "body": notes,
                "prerelease": prerelease,
                "draft": True,
            },
        )

    def set_release_notes(self, tag: str, notes: str, prerelease: bool) -> None:
        """Set the release notes for a given tag in the release description."""
        self.api_patch(
            f"/repos/{self.repository()}/releases/{self.release_id(tag)}",
            json={
                "body": notes,
                "tag_name": tag,
                "prerelease": prerelease,
            },
        )

    def release_is_published(self, tag: str) -> bool:
        """Check if the release with the given tag is published."""
        rid = self.get_release_id(tag)
        if rid is None:
            return False
        return (
            self.api_uncached(f"/repos/{self.repository()}/releases/{rid}")[
                "published_at"
            ]
            is not None
        )

    def head_ref(self) -> str:
        return os.getenv("GITHUB_HEAD_REF") or self.git.current_branch()

    def pr_number(self) -> int:
        return int(
            self.api(
                f"/repos/{self.repository()}/pulls",
                params=(("head", f"{self.actor()}:{self.head_ref()}"),),
            )[0]["number"]
        )

    def ref_name(self) -> str:
        return os.getenv("GITHUB_REF_NAME") or f"{self.pr_number()}/merge"

    def pr(self) -> Any:
        return self.api(
            f"/repos/{self.repository()}/pulls/{self.ref_name().split('/')[0]}"
        )

    def pr_branch(self) -> str:
        return str(self.pr()["head"]["ref"])

    def base_ref(self) -> str:
        return os.getenv("GITHUB_BASE_REF") or str(self.pr()["base"]["ref"])

    def base_branch(self) -> str:
        remotes = self.git.remotes()
        if "upstream" in remotes:
            return f"upstream/{self.base_ref()}"
        elif "origin" in remotes:
            return f"origin/{self.base_ref()}"
        raise ValueError("No upstream or origin remotes found")


DEFAULT_GITHUB = GitHub()


def username() -> str | None:
    return DEFAULT_GITHUB.username()


def get_release_id(tag: str) -> int | None:
    return DEFAULT_GITHUB.get_release_id(tag)


def release_id(tag: str) -> int:
    return DEFAULT_GITHUB.release_id(tag)


def actor() -> str:
    return DEFAULT_GITHUB.actor()


def milestones() -> dict[str, Milestone]:
    return DEFAULT_GITHUB.milestones()


def milestone(title: str) -> Milestone:
    return DEFAULT_GITHUB.milestone(title)


def next_milestone() -> Milestone:
    return DEFAULT_GITHUB.next_milestone()


def assign_milestone(issue_id: int, milestone: int) -> None:
    DEFAULT_GITHUB.assign_milestone(issue_id, milestone)


def close_milestone(number: int) -> None:
    DEFAULT_GITHUB.close_milestone(number)


def open_milestone_issues(milestone: int) -> list[Issue]:
    return DEFAULT_GITHUB.open_milestone_issues(milestone)


def get_issue(issue_number: int) -> Issue:
    return DEFAULT_GITHUB.get_issue(issue_number)


def rename_issue(issue_number: int, title: str) -> None:
    DEFAULT_GITHUB.rename_issue(issue_number, title)


def close_issue(issue_number: int) -> None:
    DEFAULT_GITHUB.close_issue(issue_number)


def latest_release() -> str:
    return DEFAULT_GITHUB.latest_release()


def prereleases(version: str) -> list[str]:
    return DEFAULT_GITHUB.prereleases(version)


def release_candidates(version: str) -> list[int]:
    return DEFAULT_GITHUB.release_candidates(version)


def issue_assign(issue_id: int, assignees: list[str]) -> None:
    DEFAULT_GITHUB.issue_assign(issue_id, assignees)


def issue_unassign(issue_id: int, assignees: list[str]) -> None:
    DEFAULT_GITHUB.issue_unassign(issue_id, assignees)


def create_pr(
    title: str, body: str, head: str, base: str, milestone: int
) -> PullRequest:
    return DEFAULT_GITHUB.create_pr(title, body, head, base, milestone)


def find_pr(head_sha: str, base: str) -> PullRequest | None:
    return DEFAULT_GITHUB.find_pr(head_sha, base)


def find_pr_for_branch(head: str, base: str, state: str = "all") -> PullRequest | None:
    return DEFAULT_GITHUB.find_pr_for_branch(head, base, state)


def change_pr(number: int, changes: dict[str, str | int]) -> None:
    DEFAULT_GITHUB.change_pr(number, changes)


def change_issue(number: int, changes: dict[str, str | int]) -> None:
    DEFAULT_GITHUB.change_issue(number, changes)


def checks(commit: str) -> dict[str, CheckRun]:
    return DEFAULT_GITHUB.checks(commit)


def action_runs(branch: str, head_sha: str) -> list[ActionRun]:
    return DEFAULT_GITHUB.action_runs(branch, head_sha)


def download_artifact(name: str, run_id: int) -> bytes:
    return DEFAULT_GITHUB.download_artifact(name, run_id)


def release_assets(tag: str) -> list[ReleaseAsset]:
    return DEFAULT_GITHUB.release_assets(tag)


def download_asset(asset_id: int) -> bytes:
    return DEFAULT_GITHUB.download_asset(asset_id)


def upload_asset(
    tag: str, filename: str, content_type: str, data: bytes | IO[bytes]
) -> None:
    DEFAULT_GITHUB.upload_asset(tag, filename, content_type, data)


def mark_ready_for_review(pr_node_id: str) -> None:
    DEFAULT_GITHUB.mark_ready_for_review(pr_node_id)


def push_signed(
    slug: types.RepoSlug, commit_sha: str, head_branch: str, target_branch: str
) -> str:
    return DEFAULT_GITHUB.push_signed(slug, commit_sha, head_branch, target_branch)


def tag(slug: types.RepoSlug, commit_sha: str, tag_name: str, tag_message: str) -> str:
    return DEFAULT_GITHUB.tag(slug, commit_sha, tag_name, tag_message)


def set_release_notes(tag: str, notes: str, prerelease: bool) -> None:
    DEFAULT_GITHUB.set_release_notes(tag, notes, prerelease)


def release_is_published(tag: str) -> bool:
    return DEFAULT_GITHUB.release_is_published(tag)


def repository() -> str:
    return DEFAULT_GITHUB.repository()


def repository_name() -> str:
    return DEFAULT_GITHUB.repository_name()


def head_ref() -> str:
    return DEFAULT_GITHUB.head_ref()


def pr_number() -> int:
    return DEFAULT_GITHUB.pr_number()


def ref_name() -> str:
    return DEFAULT_GITHUB.ref_name()


def pr() -> Any:
    return DEFAULT_GITHUB.pr()


def pr_branch() -> str:
    return DEFAULT_GITHUB.pr_branch()


def base_ref() -> str:
    return DEFAULT_GITHUB.base_ref()


def base_branch() -> str:
    return DEFAULT_GITHUB.base_branch()


def api_url() -> str:
    return DEFAULT_GITHUB._api_url


def api(
    url: str,
    auth: AuthLevel = AuthLevel.OPTIONAL,
    params: tuple[tuple[str, str | int], ...] = tuple(),
) -> Any:
    return DEFAULT_GITHUB.api(url, auth, params)


def clear_cache() -> None:
    DEFAULT_GITHUB.clear_cache()


def patch_markdown_section(body: str, header: str, content: str) -> str:
    """Patch a specific section in a Markdown body.

    The section is identified by its header (e.g. "### Release progress").
    If the section exists, its content is replaced.
    If it doesn't exist, it is prepended to the body.
    """
    lines = body.splitlines()
    start_index = -1
    end_index = -1

    header_level = len(header) - len(header.lstrip("#"))

    for i, line in enumerate(lines):
        if line.startswith(header):
            start_index = i
            # Find the next header of the same or higher level
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("#"):
                    next_header_level = len(lines[j]) - len(lines[j].lstrip("#"))
                    if next_header_level <= header_level:
                        end_index = j
                        break
            if end_index == -1:
                end_index = len(lines)
            break

    # Normalize content: ensure it ends with a newline and is stripped
    content = content.strip()
    new_section = [header, content, ""]

    if start_index != -1:
        # Replace existing section
        return (
            "\n".join(lines[:start_index] + new_section + lines[end_index:]).strip()
            + "\n"
        )
    else:
        # Prepend new section
        return "\n".join(new_section + lines).strip() + "\n"
