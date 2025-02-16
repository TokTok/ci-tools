#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import argparse
import os
import re
import subprocess  # nosec
from dataclasses import dataclass
from typing import Optional

import create_tarballs
import sign_release_assets
import validate_pr
import verify_release_assets
from lib import changelog
from lib import git
from lib import github
from lib import stage

BRANCH_PREFIX = git.RELEASE_BRANCH_PREFIX


@dataclass
class Config:
    branch: str
    main_branch: str
    dryrun: bool
    force: bool
    github_actions: bool
    issue: int
    production: bool
    rebase: bool
    resume: bool
    verify: bool
    version: str
    upstream: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Run a bunch of checks to validate a PR. This script is meant to be run in a
    GitHub Actions workflow, but can also be run locally.
    """)
    parser.add_argument(
        "--branch",
        help="The branch to build the release from. Default: master",
        default="master",
    )
    parser.add_argument(
        "--main-branch",
        help="The branch to merge the release branch into. Default: master",
        default="master",
    )
    parser.add_argument(
        "--dryrun",
        action=argparse.BooleanOptionalAction,
        help="Do not push changes to origin.",
        default=False,
    )
    parser.add_argument(
        "--force",
        action=argparse.BooleanOptionalAction,
        help="Force-push the release branch to origin (default on).",
        default=True,
    )
    parser.add_argument(
        "--github-actions",
        action=argparse.BooleanOptionalAction,
        help="Running in GitHub Actions.",
        default=False,
    )
    parser.add_argument(
        "--issue",
        type=int,
        help=("Number of the release tracking issue. Default: none. "
              "Required if running in GitHub Actions."),
        default=0,
    )
    parser.add_argument(
        "--production",
        action=argparse.BooleanOptionalAction,
        help=("Build a production release. "
              "If false (default), build a release candidate."),
        default=False,
    )
    parser.add_argument(
        "--rebase",
        action=argparse.BooleanOptionalAction,
        help="Rebase the release branch onto the base branch (default on).",
        default=True,
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        help="Skip manual input steps where possible.",
        default=False,
    )
    parser.add_argument(
        "--verify",
        action=argparse.BooleanOptionalAction,
        help="CI-mode: check that the release branch makes sense.",
        default=False,
    )
    parser.add_argument(
        "--version",
        help="Version to release. The special value 'latest' means the "
        "current latest release on GitHub. Default: next milestone",
        default="",
    )
    parser.add_argument(
        "--upstream",
        help="The name of the upstream remote. Default: upstream",
        default="upstream",
    )
    return Config(**vars(parser.parse_args()))


def require(condition: bool, message: Optional[str] = None) -> None:
    if not condition:
        raise stage.InvalidState(message or "Requirement not met")


def assign_to_user(s: stage.Stage, issue_id: int,
                   action: str) -> stage.UserAbort:
    """Assign the issue to the acting user for them to take some action."""
    issue = github.get_issue(issue_id)
    github.issue_unassign(issue.number, ["toktok-releaser"])
    github.issue_assign(issue.number, [github.actor()])
    s.ok(f"Assigned to {github.actor()}")
    return stage.UserAbort(f"Returning to the user to {action}")


def stage_init(config: Config) -> None:
    if config.github_actions and not config.issue:
        raise ValueError(
            "Issue number is required when running in GitHub Actions")
    if config.issue:
        with stage.Stage("Check issue",
                         "Checking the release tracking issue") as s:
            issue = github.get_issue(config.issue)
            if "toktok-releaser" not in issue.assignees:
                s.ok(f"Release issue {issue.html_url} is assigned to "
                     f"{issue.assignees}, not toktok-releaser.")
                raise stage.UserAbort("Assign the issue to toktok-releaser")
            if not issue.title.startswith("Release tracking issue"):
                # This is not a release issue.
                raise assign_to_user(s, config.issue, "deal with the issue")
            config.production = "Production release" in issue.body.splitlines()
            s.ok(f"Processing release issue {issue.html_url}")


def stage_version(config: Config) -> str:
    upstream = list({config.upstream, "origin"})
    with stage.Stage("Fetch upstream",
                     f"Fetching tags and branches from {upstream}") as s:
        git.fetch(*upstream)
        if config.branch == config.main_branch and git.branch_sha(
                "HEAD") != git.branch_sha(
                    f"{config.upstream}/{config.branch}"):
            git.pull(config.upstream)
        s.ok(git.branch_sha(f"{config.upstream}/{config.main_branch}")[:7])
    with stage.Stage("Version", "Determine the upcoming version") as s:
        if config.issue:
            issue = github.get_issue(config.issue)
            if issue.title.startswith("Release tracking issue: "):
                config.version = issue.title.split(": ", 1)[1]
        if config.version:
            if config.version == "latest":
                version = github.latest_release()
                s.ok(f"Using latest release {version}")
                return version

            require(
                re.match(git.VERSION_REGEX, config.version) is not None,
                f"Invalid version: {config.version} "
                f"(expected: {git.VERSION_REGEX.pattern})",
            )
            s.ok(f"Accepting override version {config.version}")
            return config.version
        version = github.next_milestone().title
        if not config.production:
            # This is a prerelease, so we need to find the latest prerelease.
            rc = max(github.release_candidates(version), default=0)
            version = f"{version}-rc.{rc + 1}"
        require(re.match(git.VERSION_REGEX, version) is not None)
        s.ok(version)
    return version


def release_commit_message(version: str) -> str:
    return f"chore: Release {version}"


def release_issue_title(version: str) -> str:
    return f"Release tracking issue: {version}"


def stage_branch(config: Config, version: str) -> None:
    with stage.Stage("Create release branch",
                     "Creating a release branch") as s:
        release_branch = f"{BRANCH_PREFIX}/{version}"
        if release_branch in git.branches() or release_branch in git.branches(
                "origin"):
            git.checkout(release_branch)
            if not config.rebase:
                action = "skipping rebase"
            else:
                rebased = git.last_commit_message(
                    release_branch) == release_commit_message(version)
                if rebased:
                    if git.rebase(config.branch, commits=1):
                        action = f"rebased onto {config.branch}"
                    else:
                        action = f"already on {config.branch}"
                else:
                    git.reset(config.branch)
                    action = f"reset to {config.branch}"
            s.ok(f"Branch '{release_branch}' already exists; {action}")
        else:
            git.create_branch(release_branch, config.branch)
            s.ok(f"Branch '{release_branch}' created "
                 f"@ {git.branch_sha(release_branch)[:7]}")
        require(git.current_branch() == release_branch, git.current_branch())


def stage_validate(config: Config) -> None:
    validate_pr.main(validate_pr.Config(commit=not config.verify))


def extract_issue_release_notes(body: str) -> str:
    """Extract the release notes from the issue body."""
    start = body.find("### Release notes")
    if start == -1:
        return ""
    end = body.find("### ", start + 1)
    return body[start:end].strip()


def stage_release_notes(config: Config, version: str) -> None:
    """Opens $EDITOR (from environment, or vim) to edit the release notes in CHANGELOG.md."""
    with stage.Stage("Write release notes", "Opening editor") as s:
        if config.resume and changelog.has_release_notes(version):
            s.ok("Skipping")
        elif config.github_actions:
            m = github.next_milestone()
            tracking_issue = [
                issue for issue in github.open_milestone_issues(m.number)
                if "toktok-releaser" in issue.assignees
            ]
            if not tracking_issue:
                raise s.fail("No tracking issue found")
            if len(tracking_issue) > 1:
                raise s.fail(
                    "Multiple tracking issues found: "
                    f"{', '.join(i.html_url for i in tracking_issue)}")
            issue = tracking_issue[0]
            notes = extract_issue_release_notes(issue.body)
            if not notes:
                raise s.fail("No release notes found in issue body")
            changelog.set_release_notes(version, notes)
            git.add("CHANGELOG.md")
            s.ok(f"Release notes copied from {issue.html_url}")
        else:
            editor = os.getenv("EDITOR") or "vim"
            subprocess.run([editor, "CHANGELOG.md"], check=True)  # nosec
            git.add("CHANGELOG.md")
            s.ok()


def stage_commit(version: str) -> None:
    with stage.Stage("Commit changes", "Committing changes") as s:
        release_notes = changelog.get_release_notes(version).notes + "\n"
        if git.is_clean():
            s.ok("No changes to commit")
            return

        changes = git.changed_files()
        git.commit(release_commit_message(version), release_notes)
        s.ok(str(changes))


def stage_push(config: Config) -> None:
    with stage.Stage("Push changes", "Pushing changes to origin") as s:
        release_branch = git.current_branch()
        if git.is_up_to_date(release_branch, config.upstream):
            s.ok("No changes to push")
            return

        if config.dryrun:
            s.ok("Dry run; not pushing changes")
        elif config.github_actions:
            sha = github.push_signed(
                git.remote_slug(config.upstream),
                git.branch_sha(release_branch),
                config.main_branch,
                release_branch,
            )
            git.fetch(config.upstream)
            git.reset(sha)
            s.ok(sha)
        else:
            git.push("origin", git.current_branch(), force=config.force)
            s.ok()


RELEASER_START = "<!-- Releaser:start -->"
RELEASER_END = "<!-- Releaser:end -->"


def get_pr_body(body: str) -> str:
    """
    <!-- Releaser:start -->
    Actual body goes here.
    <!-- Releaser:end -->
    """
    start = body.find(RELEASER_START)
    end = body.find(RELEASER_END)
    if start == -1 or end == -1:
        return ""
    return body[start + len(RELEASER_START):end].strip()


def patch_pr_body(body: str, patch: str) -> str:
    start = body.find(RELEASER_START)
    end = body.find(RELEASER_END)
    if start == -1 or end == -1:
        return f"{RELEASER_START}\n{patch}\n{RELEASER_END}\n{body}"
    return f"{body[:start]}{RELEASER_START}\n{patch}\n{RELEASER_END}\n{body[end + len(RELEASER_END):]}"


def pr_patch(pr: github.PullRequest, title: str, body: str,
             milestone: int) -> dict[str, str | int]:
    patch: dict[str, str | int] = {}
    if pr.state != "open":
        patch["state"] = "open"
    if pr.title != title:
        patch["title"] = title
    if pr.milestone != milestone:
        patch["milestone"] = milestone
    if get_pr_body(pr.body) != body:
        patch["body"] = patch_pr_body(pr.body, body)
    return patch


def stage_pull_request(
    config: Config,
    version: str,
) -> Optional[github.PullRequest]:
    with stage.Stage("Create pull request",
                     "Creating a pull request on GitHub") as s:
        title = f"chore: Release {version}"
        body = changelog.get_release_notes(version).notes
        head = f"{git.owner('origin')}:{BRANCH_PREFIX}/{version}"
        base = config.main_branch
        milestone = github.next_milestone()
        existing_pr = github.find_pr_for_branch(head, base, "open")
        if config.dryrun:
            s.ok("Dry run; not creating a pull request")
            print(f"title: {title}")
            print(f"body: {body}")
            print(f"head: {head}")
            print(f"base: {base}")
            print(f"milestone: {milestone}")
            if existing_pr:
                print(f"Existing PR: {existing_pr.html_url}")
            return None

        if existing_pr:
            patch = pr_patch(existing_pr, title, body, milestone.number)
            if not patch:
                s.ok(f"PR already exists: {existing_pr.html_url}")
                return existing_pr

            github.change_pr(existing_pr.number, patch)
            if "milestone" in patch:
                # Milestone is on issue, not PR.
                github.change_issue(existing_pr.number,
                                    {"milestone": patch["milestone"]})
            s.ok(f"Modified PR: {existing_pr.html_url}")
            return existing_pr

        s.progress(f"Creating PR: {title} ({head} -> {base}) "
                   f"on milestone {milestone.number}")
        pr = github.create_pr(title, patch_pr_body("", body), head, base,
                              milestone.number)
        s.ok(pr.html_url)
        return pr


def stage_restyled(config: Config, version: str, parent: stage.Stage) -> None:
    if config.verify:
        # Can't do this on CI.
        return
    with stage.Stage("Restyled", "Applying restyled fixes",
                     parent=parent) as s:
        subprocess.run(["hub-restyled"], check=True)  # nosec
        if git.is_clean():
            raise s.fail("Failed to apply restyled changes")
        git.add(".")
        stage_commit(version)
        stage_push(config)
        s.ok("Restyled changes applied")


def get_head_pr(config: Config, version: str) -> Optional[github.PullRequest]:
    sha = git.find_commit_sha(release_commit_message(version))
    return github.find_pr(sha, config.main_branch)


def await_head_pr(config: Config, s: stage.Stage,
                  version: str) -> github.PullRequest:
    """Wait for the PR to be synced with the head sha."""
    for _ in range(10):
        pr = get_head_pr(config, version)
        if pr:
            return pr
        s.progress(f"Waiting for release PR for {version}")
        stage.sleep(5)
    raise ValueError("Timeout waiting for PR to be created/updated")


def stage_await_checks(config: Config, version: str) -> None:
    with stage.Stage("Await checks", "Waiting for checks to pass") as s:
        for _ in range(120):  # 120 * 30s = 1 hour
            pr = await_head_pr(config, s, version)

            checks = github.checks(pr.head_sha)
            if not checks:
                s.progress("Awaiting checks to start")
                stage.sleep(10)
                continue

            if config.verify:
                # Remove "Verify release/signatures" check if we are
                # running on CI (this is our own check).
                del checks["Verify release/signatures"]

            completed = [
                c.name for c in checks.values() if c.status == "completed"
            ]
            progress = [
                c.name for c in checks.values() if c.status == "in_progress"
            ]
            success = [
                c.name for c in checks.values() if c.conclusion == "success"
            ]
            failures = [
                c.name for c in checks.values() if c.conclusion == "failure"
            ]
            neutral = [
                c.name for c in checks.values() if c.conclusion == "neutral"
            ]

            if len(completed) == len(checks):
                if failures:
                    raise s.fail(f"{len(failures)} checks failed on "
                                 f"{pr.html_url}: {', '.join(failures)}")
                s.ok(f"All {len(completed)} checks passed")
                return

            s.progress(f"{len(success)} checks passed"
                       f", {len(neutral)} checks neutral"
                       f", {len(failures)} failed"
                       f", {len(progress)} in progress")
            if ("common / restyled" in checks
                    and checks["common / restyled"].conclusion == "failure"):
                stage_restyled(config, version, parent=s)

            stage.sleep(30)

        raise s.fail("Timeout waiting for checks to pass")


def stage_production_ready(config: Config, version: str) -> None:
    """For production releases, check whether there are any more issues in the milestone.

    For release candidates, we allow more issues to be on the milestone's todo list.
    """
    with stage.Stage("Production ready",
                     "Checking if the release has any more open issues") as s:
        if config.production:
            m = github.next_milestone()
            issues = [
                i for i in github.open_milestone_issues(m.number)
                if i.title != release_commit_message(version)
                and i.number != config.issue
            ]
            if issues:
                raise s.fail(f"{len(issues)} issues are still open for "
                             f"{version}: {m.html_url}")
            s.ok(f"No open issues for {version}")
        else:
            s.ok("Release candidate; not checking milestone")


def stage_rename_issue(config: Config, version: str) -> None:
    with stage.Stage("Rename issue",
                     "Renaming the release tracking issue") as s:
        if not config.issue:
            s.ok("No issue to rename")
            return
        title = release_issue_title(version)
        issue = github.get_issue(config.issue)
        if issue.title == title:
            s.ok(f"Issue already named '{title}'")
            return
        github.rename_issue(config.issue, title)
        s.ok(f"Issue renamed to '{title}'")


def stage_ready_for_review(config: Config, version: str) -> None:
    with stage.Stage("Ready for review",
                     "Marking PR as ready for review") as s:
        pr = get_head_pr(config, version)
        if not pr:
            raise s.fail("PR not found")
        if pr.draft:
            github.mark_ready_for_review(pr.node_id)
            s.ok(f"PR {pr.number} is now ready for review")
        else:
            s.ok(f"PR {pr.number} is already ready for review")


def stage_await_merged(config: Config, version: str) -> None:
    """Wait for the PR to be merged by toktok-releaser.

    We don't merge the PR ourselves, but wait for automerge to do it.
    """
    with stage.Stage("Await merged", "Waiting for the PR to be merged") as s:
        for _ in range(120):  # 120 * 30s = 1 hour
            pr = get_head_pr(config, version)
            if not pr:
                raise s.fail(f"PR not found for {version}")
            if pr.state == "closed":
                if pr.merged:
                    s.ok(f"PR {pr.number} was merged")
                    git.checkout(config.main_branch)
                    git.pull(config.upstream)
                    return
                raise s.fail(f"PR {pr.number} was closed without being merged")
            elif pr.state == "open":
                s.progress(f"PR {pr.number} is still open")
            else:
                s.progress(f"PR {pr.number} is {pr.state}")
            stage.sleep(30)
        raise s.fail("Timeout waiting for PR to be merged")


def stage_await_master_build(config: Config, version: str) -> None:
    """Wait for the master branch to be built."""
    with stage.Stage(
            "Await master build",
            f"Waiting for the {config.main_branch} branch to be built",
    ) as s:
        for _ in range(120):  # 120 * 30s = 1 hour
            head_sha = git.branch_sha(config.main_branch)
            builds = [
                run for run in github.action_runs(config.main_branch, head_sha)
                if run.event != "issues"
            ]
            if not builds:
                s.progress(
                    f"Waiting for builds to start for {config.main_branch}")
                stage.sleep(10)
                continue
            for build in builds:
                if build.conclusion == "failure":
                    raise s.fail(
                        f"Main branch failed to build: {build.html_url}")
            builds = [build for build in builds if build.status != "completed"]
            if not builds:
                s.ok("Main branch built")
                return
            s.progress(f"Main branch still building: {builds[0].html_url}")
            stage.sleep(30)
        raise s.fail(
            f"Timeout waiting for {config.main_branch} branch to be built")


def stage_tag(config: Config, version: str) -> None:
    """Tag the release with and push it to upstream."""
    with stage.Stage("Tag release", "Tagging the release") as s:
        release_notes = changelog.get_release_notes(version).notes + "\n"
        if git.release_tag_exists(version):
            s.progress(f"Tag {version} already exists")
            if config.github_actions:
                s.ok("No tag push required")
                return
        else:
            git.tag(version, release_notes, sign=not config.github_actions)
            s.progress(f"Tagged {version}")

        if config.dryrun:
            s.ok("Dry run; not pushing tag")
        elif config.github_actions and not config.dryrun:
            s.progress(f"Pushing tag {version} with GitHub API")
            sha = github.tag(
                git.remote_slug(config.upstream),
                git.branch_sha(version),
                version,
                release_notes,
            )
            git.fetch(config.upstream)
            s.ok(f"Tagged {version} @ {sha}")
        else:
            git.push(config.upstream, version, force=config.force)
            s.ok(f"Pushed tag {version} to {config.upstream}")


def stage_build_binaries(config: Config, version: str) -> None:
    """Wait for GitHub Actions to build the binaries.

    We wait for the workflows in the "push" event with our current head_sha.
    """
    with stage.Stage("Build binaries",
                     "Waiting for binaries to be built") as s:
        head_sha = git.branch_sha(version)
        for _ in range(6):  # 6 * 10s = 1 minute
            # Fetch the latest commits to get the latest head_sha. In case we're
            # running on GitHub Actions, we need to wait for a human to sign the
            # tag, which will have a different head_sha.
            git.fetch(config.upstream)
            head_sha = git.branch_sha(version)
            builds = [run for run in github.action_runs(version, head_sha)]
            if builds:
                break
            s.progress("Waiting for builds to start for "
                       f"{version} @ {head_sha}")
            stage.sleep(10)
        else:
            if config.github_actions:
                s.ok("No builds found; waiting for a human to sign the tag")
                raise assign_to_user(s, config.issue, "sign the tag")

        for _ in range(120):  # 120 * 30s = 1 hour
            builds = [run for run in github.action_runs(version, head_sha)]
            if not builds:
                s.progress("Waiting for builds to start for "
                           f"{version} @ {head_sha}")
                stage.sleep(10)
                continue
            for build in builds:
                if build.conclusion == "failure":
                    raise s.fail(f"Binaries failed to build: {build.html_url}")
            todo = [build for build in builds if build.status != "completed"]
            if not todo:
                s.ok(f"Binaries built: {len(builds)} workflows completed "
                     f"for {head_sha}")
                # Clear cache so the newly created release tag is visible.
                github.clear_cache()
                return
            s.progress(f"Binaries still building: {builds[0].html_url}")
            stage.sleep(30)
        raise s.fail("Timeout waiting for binaries to be built")


def has_tarballs(version: str) -> bool:
    """Check if there are tarball assets for the given version.

    Tarball assets are $version.tar.{gz,xz}.
    """
    assets = github.release_assets(version)
    return all(
        any(a.name == f"{version}.tar.{ext}" for a in assets)
        for ext in ("gz", "xz"))


def stage_create_tarballs(version: str) -> None:
    with stage.Stage("Create tarballs", "Creating tarballs") as s:
        if has_tarballs(version):
            s.ok("Tarballs already created")
        else:
            create_tarballs.main(
                create_tarballs.Config(upload=True, tag=version))
            s.ok("Tarballs created")


def stage_sign_release_assets(config: Config, version: str) -> None:
    with stage.Stage("Sign release assets", "Signing release assets") as s:
        if config.github_actions:
            assets = sign_release_assets.todo(version)
            if not assets:
                s.ok("All release assets have been signed")
                return
            s.progress(f"{len(assets)} release assets need signing")
            raise assign_to_user(s, config.issue, "sign the assets")

        sign_release_assets.main(
            sign_release_assets.Config(upload=True, tag=version))
        s.ok("Release assets signed")


def stage_verify_release_assets(version: str) -> None:
    with stage.Stage("Verify release assets", "Verifying release assets") as s:
        verify_release_assets.main(verify_release_assets.Config(tag=version))
        s.ok("Release assets verified")


def stage_format_release_notes(config: Config, version: str) -> None:
    with stage.Stage("Format release notes",
                     "Formatting release notes on GitHub release") as s:
        release_notes = changelog.get_release_notes(version)
        github.set_release_notes(
            version,
            release_notes.formatted(),
            prerelease=not config.production,
        )
        s.ok("Release notes formatted")


def stage_publish_release(config: Config, version: str) -> None:
    with stage.Stage("Publish release", "Publishing the release") as s:
        if github.release_is_published(version):
            s.ok("Release already published")
            return
        if config.github_actions:
            s.ok("Asking user to publish the release")
            raise assign_to_user(s, config.issue, "publish the release")
        s.ok("Not implemented yet")


def stage_close_milestone(config: Config, version: str) -> None:
    with stage.Stage("Close milestone", "Closing the release milestone") as s:
        if not config.production:
            s.ok("Not closing milestone for release candidate")
            return
        m = github.next_milestone()
        if m.title != version:
            raise s.fail(f"Milestone {m.title} is not the next milestone")
        github.close_milestone(m.number)
        s.ok(f"Milestone {m.title} closed")


def stage_close_issue(config: Config) -> None:
    with stage.Stage("Close issue", "Closing the release tracking issue") as s:
        if not config.issue:
            s.ok("No issue to close")
            return
        issue = github.get_issue(config.issue)
        if issue.state == "closed":
            s.ok("Issue already closed")
            return
        github.close_issue(config.issue)
        s.ok(f"Issue {config.issue} closed")


def run_stages(config: Config) -> None:
    require(git.current_branch() == config.branch)
    require(git.is_clean())

    stage_init(config)

    version = stage_version(config)
    stage_rename_issue(config, version)
    stage_production_ready(config, version)

    if release_commit_message(version) not in git.log(config.main_branch):
        stage_branch(config, version)
        stage_validate(config)
        stage_release_notes(config, version)
        stage_commit(version)
        stage_push(config)
        stage_pull_request(config, version)
        stage_await_checks(config, version)
        if config.verify:
            # We're done for now. On CI, we're not allowed to mark the PR as
            # ready for review, so we just end the checks here.
            return
        stage_ready_for_review(config, version)
    else:
        print(f"Release branch {BRANCH_PREFIX}/{version} already merged.",
              flush=True)
    stage_await_merged(config, version)
    stage_await_master_build(config, version)
    stage_tag(config, version)
    stage_build_binaries(config, version)
    stage_create_tarballs(version)
    stage_sign_release_assets(config, version)
    stage_verify_release_assets(version)
    stage_format_release_notes(config, version)
    stage_publish_release(config, version)
    stage_close_milestone(config, version)
    stage_close_issue(config)


def main(config: Config) -> None:
    # chdir into the root of the repository.
    os.chdir(git.root())
    # We need auth to get the draft release etc.
    print("Building release as GitHub user", github.actor())
    try:
        # Stash any local changes for the user to later resume working on.
        with git.Stash():
            # We need to be on the main branch to create a release, but we
            # want to return to the original branch afterwards.
            with git.Checkout(config.branch):
                # Undo any partial changes if the script is aborted.
                with git.ResetOnExit():
                    run_stages(config)
    except stage.UserAbort as e:
        print(e.message)
        return


if __name__ == "__main__":
    main(parse_args())
