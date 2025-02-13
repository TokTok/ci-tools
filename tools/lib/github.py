#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import os
import re
from dataclasses import dataclass
from functools import cache as memoize
from typing import Any
from typing import IO
from typing import Optional

import requests
from lib import git


@memoize
def github_token() -> Optional[str]:
    token = os.getenv("GITHUB_TOKEN")
    if token:
        print("Authorization with GITHUB_TOKEN")
    else:
        print("Unauthorized (low rate limit applies)")
        print("Set GITHUB_TOKEN to increase the rate limit")
    return token


def auth_headers(required: bool) -> dict[str, str]:
    """Get the authentication headers for GitHub.

    If the GITHUB_TOKEN environment variable is not set, this function will
    raise an error if required is True, or return an empty dictionary if
    required is False.
    """
    token = github_token()
    if not token:
        if required:
            raise ValueError("GITHUB_TOKEN is needed to upload tarballs")
        else:
            return {}
    return {"Authorization": f"Token {token}"}


api_requests: list[str] = []


def api_url() -> str:
    return os.getenv("GITHUB_API_URL") or "https://api.github.com"


def api_uncached(
        url: str,
        auth: bool = False,
        params: tuple[tuple[str, str | int], ...] = tuple(),
) -> Any:
    """Call the GitHub API with the given URL (GET only).

    Not cached, use the api() function to cache calls.
    """
    api_requests.append(f"GET {api_url()}{url}")
    response = requests.get(
        f"{api_url()}{url}",
        headers=auth_headers(required=auth),
        params=dict(params),
    )
    response.raise_for_status()
    return response.json()


@memoize
def api(
        url: str,
        auth: bool = False,
        params: tuple[tuple[str, str | int], ...] = tuple(),
) -> Any:
    """Cache-calls the GitHub API with the given URL (GET only).

    Authorization is done with the GITHUB_TOKEN environment variable if it is set.

    Args:
        url: The URL to call, starting with a slash.
        auth: Whether authorization is required (will raise an exception if no token is available).
        params: A list of key-value pairs to pass as query parameters.
    """
    return api_uncached(url, auth, params)


def username() -> Optional[str]:
    """Get the GitHub username for the current authenticated user."""
    if not github_token():
        return None
    return str(api("/user", auth=True)["login"])


@memoize
def release_id(tag: str) -> int:
    """Get the GitHub release ID number for a tag.

    Also works for draft releases. We use tag_name instead of tag because
    draft releases are untagged.
    """
    for release in api(f"/repos/{repository()}/releases"):
        if release["tag_name"] == tag:
            return int(release["id"])
    raise ValueError(f"Release {tag} not found")


def head_ref() -> str:
    """Calls git rev-parse --abbrev-ref HEAD to get the current branch name."""
    return os.getenv("GITHUB_HEAD_REF") or git.current_branch()


def actor() -> str:
    """Returns the GitHub username for the current repository."""
    return os.getenv("GITHUB_ACTOR") or username() or git.remote_slug(
        "origin").name


def repository() -> str:
    return os.getenv("GITHUB_REPOSITORY") or str(git.remote_slug("upstream"))


def pr_number() -> int:
    """Calls the GitHub API to get the PR number for the current branch.

    Requires the GITHUB_API_URL and GITHUB_REF environment variables to be set.
    """
    return int(
        api(
            f"/repos/{repository()}/pulls",
            params=(("head", f"{actor()}:{head_ref()}"), ),
        )[0]["number"])


def ref_name() -> str:
    return os.getenv("GITHUB_REF_NAME") or f"{pr_number()}/merge"


def pr() -> Any:
    """Calls the GitHub API to get the current PR object."""
    return api(f"/repos/{repository()}/pulls/{ref_name().split('/')[0]}")


def pr_branch() -> str:
    """Calls the GitHub API to get the branch name for the current PR."""
    return str(pr()["head"]["ref"])


def base_ref() -> str:
    """Calls the GitHub API to get the base branch for the current PR."""
    return os.getenv("GITHUB_BASE_REF") or str(pr()["base"]["ref"])


def base_branch() -> str:
    """Get the base ref with its remote path."""
    remotes = git.remotes()
    if "upstream" in remotes:
        return f"upstream/{base_ref()}"
    elif "origin" in remotes:
        return f"origin/{base_ref()}"
    raise ValueError("No upstream or origin remotes found")


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


def milestones() -> dict[str, Milestone]:
    """Get the names and IDs of all milestones in the repository."""
    return {
        m["title"]: Milestone.fromJSON(m)
        for m in api(f"/repos/{repository()}/milestones")
    }


def next_milestone() -> Milestone:
    """Get the next release number (based on the smallest open milestone).

    Milestones are formatted like v1.18.0 or v1.18.x (ignored). The next
    release number is the smallest version number in the milestones list.
    """
    return min(
        (m for m in milestones().values()
         if re.match(r"v\d+\.\d+\.\d+$", m.title)),
        key=lambda m: tuple(map(int, m.title[1:].split("."))),
    )


@dataclass
class Issue:
    title: str
    number: int
    html_url: str
    state: str
    milestone: Optional[int]

    @staticmethod
    def fromJSON(issue: dict[str, Any]) -> "Issue":
        return Issue(
            title=str(issue["title"]),
            number=int(issue["number"]),
            html_url=str(issue["html_url"]),
            state=str(issue["state"]),
            milestone=int(issue["milestone"]["number"])
            if issue["milestone"] else None,
        )


def open_milestone_issues(milestone: int) -> list[Issue]:
    """Get all the open issues for a given milestone."""
    return [
        Issue.fromJSON(i) for i in api(
            f"/repos/{repository()}/issues",
            params=(
                ("milestone", milestone),
                ("state", "open"),
            ),
        )
    ]


def latest_release() -> str:
    """Get the name of the current release in the repository.

    Includes prereleases.
    """
    return str(api(f"/repos/{repository()}/releases/latest")["tag_name"])


def prereleases(version: str) -> list[str]:
    """Get the names of all prereleases for a given version in the repository."""
    return [
        r["tag_name"] for r in api(f"/repos/{repository()}/releases")
        if f"{version}-rc." in r["tag_name"] and r["prerelease"]
        and not r["draft"]
    ]


def release_candidates(version: str) -> list[int]:
    """Get the RC numbers (the number after "-rc.") for prereleases of a given version."""
    return [
        int(i) for r in prereleases(version)
        for i in re.findall(r"-rc\.(\d+)$", r)
    ]


@dataclass
class PullRequest:
    title: str
    body: str
    number: int
    node_id: str
    html_url: str
    state: str
    head_sha: str
    milestone: Optional[int]
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
            milestone=int(pr["milestone"]["number"])
            if pr["milestone"] else None,
            draft=bool(pr["draft"]),
            merged=pr["merged_at"] is not None,
        )


def create_pr(title: str, body: str, head: str, base: str,
              milestone: int) -> PullRequest:
    """Create a pull request with the given title and body.

    Returns the URL of the created PR.
    """
    response = requests.post(
        f"{api_url()}/repos/{repository()}/pulls",
        headers=auth_headers(True),
        json={
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": True,
        },
    )
    response.raise_for_status()
    pr = PullRequest.fromJSON(response.json())
    if milestone:
        change_issue(pr.number, {"milestone": milestone})
    return pr


def find_pr(head_sha: str, base: str) -> Optional[PullRequest]:
    """Find a PR with the given title, head.sha, and base."""
    # The HEAD sha may be updated, so we can't use cached API calls.
    response = api_uncached(
        f"/repos/{repository()}/pulls",
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


def find_pr_for_branch(head: str, base: str) -> Optional[PullRequest]:
    """Find a PR with the given head (actor:branch) and base."""
    # The branch may be updated, so we can't use cached API calls.
    response = api_uncached(
        f"/repos/{repository()}/pulls",
        params=(
            ("state", "all"),
            ("base", base),
            ("head", head),
            ("per_page", 100),
        ),
    )
    return PullRequest.fromJSON(response[0]) if response else None


def change_pr(number: int, changes: dict[str, str | int]) -> None:
    """Modify a PR with the given number (e.g. reopen by changing "state")."""
    response = requests.patch(
        f"{api_url()}/repos/{repository()}/pulls/{number}",
        headers=auth_headers(True),
        json=changes,
    )
    response.raise_for_status()


def change_issue(number: int, changes: dict[str, str | int]) -> None:
    """Modify an issue with the given number (e.g. close by changing "state").

    Also used to set milestones on pull requests.
    """
    response = requests.patch(
        f"{api_url()}/repos/{repository()}/issues/{number}",
        headers=auth_headers(True),
        json=changes,
    )
    response.raise_for_status()


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


def checks(commit: str) -> dict[str, CheckRun]:
    """Return all the GitHub Actions results."""
    # The PR may be updated, so we can't use cached API calls.
    check_runs = {
        r["name"]: CheckRun.fromJSON(r)
        for s in api_uncached(
            f"/repos/{repository()}/commits/{commit}/check-suites",
        )["check_suites"]
        for r in api_uncached(
            f"/repos/{repository()}/check-suites/{s['id']}/check-runs", )
        ["check_runs"]
    }
    return check_runs


@dataclass
class ActionRun:
    id: int
    node_id: str
    name: str
    status: str
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
            conclusion=str(run["conclusion"]),
            html_url=str(run["html_url"]),
            path=str(run["path"]),
        )


def action_runs(branch: str, head_sha: str) -> list[ActionRun]:
    """Return all the GitHub Actions results."""
    # The PR may be updated, so we can't use cached API calls.
    return [
        ActionRun.fromJSON(r) for r in api_uncached(
            f"/repos/{repository()}/actions/runs",
            params=(("branch", branch), ("head_sha", head_sha)),
        )["workflow_runs"]
    ]


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


def release_assets(tag: str) -> list[ReleaseAsset]:
    """Return all the assets for a given tag."""
    return [
        ReleaseAsset.fromJSON(a) for a in api_uncached(
            f"/repos/{repository()}/releases/{release_id(tag)}")["assets"]
    ]


def download_asset(asset_id: int) -> bytes:
    """Download the asset with the given ID."""
    response = requests.get(
        f"{api_url()}/repos/{repository()}/releases/assets/{asset_id}",
        headers={
            "Accept": "application/octet-stream",
            **auth_headers(False),
        },
    )
    response.raise_for_status()
    return response.content


def upload_asset(
    tag: str,
    filename: str,
    content_type: str,
    data: bytes | IO[bytes],
) -> None:
    """Upload an asset to the release with the given tag.

    The data should be the contents of the file to upload or a binary stream.
    """
    response = requests.post(
        f"https://uploads.github.com/repos/{repository()}/releases/{release_id(tag)}/assets",
        headers={
            "Content-Type": content_type,
            **auth_headers(required=True),
        },
        data=data,
        params={"name": filename},
    )
    response.raise_for_status()


def graphql(query: str) -> Any:
    """Call the GitHub GraphQL API with the given query."""
    response = requests.post(
        f"{api_url()}/graphql",
        headers={
            "Accept": "application/json",
            **auth_headers(required=True),
        },
        json={"query": query},
    )
    response.raise_for_status()
    return response.json()["data"]


# markPullRequestReadyForReview via graphql
def mark_ready_for_review(pr_node_id: str) -> None:
    """Mark a PR as ready for review."""
    graphql(f"""
        mutation MarkPrReady {{
            markPullRequestReadyForReview(input: {{pullRequestId: "{pr_node_id}"}}) {{
                pullRequest {{
                    id
                }}
            }}
        }}
    """)
