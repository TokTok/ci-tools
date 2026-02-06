#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2026 The TokTok team
import argparse
import os
import re
import subprocess  # nosec
from dataclasses import dataclass

import create_tarballs
import sign_release_assets
import sign_tag
import validate_pr
import verify_release_assets
from lib import changelog, git, github, stage

BRANCH_PREFIX = git.RELEASE_BRANCH_PREFIX
RELEASER_START = "<!-- Releaser:start -->"
RELEASER_END = "<!-- Releaser:end -->"


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
        help=(
            "Number of the release tracking issue. Default: none. "
            "Required if running in GitHub Actions."
        ),
        default=0,
    )
    parser.add_argument(
        "--production",
        action=argparse.BooleanOptionalAction,
        help=(
            "Build a production release. "
            "If false (default), build a release candidate."
        ),
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


class Releaser:
    def __init__(self, config: Config, git_prov: git.Git, github_prov: github.GitHub):
        self.config = config
        self.git = git_prov
        self.github = github_prov

    def require(self, condition: bool, message: str | None = None) -> None:
        if not condition:
            raise stage.InvalidState(message or "Requirement not met")

    def assign_to_user(
        self,
        s: stage.Stage,
        version: str,
        task: str | None = None,
        action: str = "",
        instruction: str | None = None,
    ) -> stage.UserAbort:
        """Assign the issue to the acting user for them to take some action."""
        self.github.issue_unassign(self.config.issue, ["toktok-releaser"])
        self.github.issue_assign(self.config.issue, [self.github.actor()])
        self.update_dashboard(version, current_task=task, instruction=instruction)
        s.ok(f"Assigned to {self.github.actor()}")
        return stage.UserAbort(f"Returning to the user to {action}")

    def compute_done_milestones(self, version: str) -> set[str]:
        """Heuristics to determine which milestones are completed."""
        done = set()

        # 1. Preparation
        if self.github.find_pr_for_branch(
            f"{self.git.owner('origin')}:{BRANCH_PREFIX}/{version}",
            self.config.main_branch,
        ):
            done.add("Preparation")

        # 2. Review
        try:
            if self.git.branch_sha(self.config.main_branch) == self.git.find_commit_sha(
                self.release_commit_message(version)
            ):
                done.add("Preparation")
                done.add("Review")
        except Exception as e:
            print(f"Heuristic for 'Review' milestone failed: {e}")

        # 3. Tagging
        if self.git.release_tag_exists(version) and self.git.tag_has_signature(version):
            done.add("Preparation")
            done.add("Review")
            done.add("Tagging")

        # 4. Binaries
        if self.has_tarballs(version) and not sign_release_assets.todo(version):
            done.add("Preparation")
            done.add("Review")
            done.add("Tagging")
            done.add("Binaries")

        # 5. Publication
        if self.github.release_is_published(version):
            done.add("Preparation")
            done.add("Review")
            done.add("Tagging")
            done.add("Binaries")
            done.add("Publication")

        return done

    def render_progress_list(
        self, done: set[str], current_task: str | None, instruction: str | None
    ) -> str:
        """Render the Markdown task list for the dashboard."""
        milestones = [
            ("Preparation", "Create release branch and PR"),
            ("Review", "Approve and merge PR"),
            ("Tagging", "Tag and sign the release"),
            ("Binaries", "Build and sign binaries"),
            ("Publication", "Finalize release"),
        ]

        lines = []
        for name, desc in milestones:
            status = "[x]" if name in done else "[ ]"
            if current_task == name:
                lines.append(f"- {status} **Current Step: {desc}**")
                if instruction:
                    lines.append(f"  > ℹ️ **Action Required:** {instruction}")
            else:
                lines.append(f"- {status} {desc}")

        return "\n".join(lines)

    def update_dashboard(
        self,
        version: str,
        current_task: str | None = None,
        instruction: str | None = None,
    ) -> None:
        if not self.config.issue or self.config.dryrun:
            return

        done = self.compute_done_milestones(version)
        content = self.render_progress_list(done, current_task, instruction)

        issue = self.github.get_issue(self.config.issue)
        new_body = github.patch_markdown_section(
            issue.body, "### Release progress", content
        )
        if new_body != issue.body:
            self.github.change_issue(self.config.issue, {"body": new_body})

    def stage_init(self) -> None:
        if self.config.github_actions and not self.config.issue:
            raise ValueError("Issue number is required when running in GitHub Actions")
        if self.config.issue:
            with stage.Stage("Check issue", "Checking the release tracking issue") as s:
                issue = self.github.get_issue(self.config.issue)
                if "toktok-releaser" not in issue.assignees:
                    s.ok(
                        f"Release issue {issue.html_url} is assigned to "
                        f"{issue.assignees}, not toktok-releaser."
                    )
                    raise stage.UserAbort("Assign the issue to toktok-releaser")
                if not issue.title.startswith("Release tracking issue"):
                    # This is not a release issue.
                    raise self.assign_to_user(s, "", action="deal with the issue")
                self.config.production = "Production release" in issue.body.splitlines()
                s.ok(f"Processing release issue {issue.html_url}")

    def stage_version(self) -> str:
        upstream = list({self.config.upstream, "origin"})
        with stage.Stage(
            "Fetch upstream", f"Fetching tags and branches from {upstream}"
        ) as s:
            self.git.fetch(*upstream)
            if self.config.branch == self.config.main_branch and self.git.branch_sha(
                "HEAD"
            ) != self.git.branch_sha(f"{self.config.upstream}/{self.config.branch}"):
                self.git.pull(self.config.upstream)
            s.ok(
                self.git.branch_sha(
                    f"{self.config.upstream}/{self.config.main_branch}"
                )[:7]
            )
        with stage.Stage("Version", "Determine the upcoming version") as s:
            if self.config.issue:
                issue = self.github.get_issue(self.config.issue)
                if issue.title.startswith("Release tracking issue: "):
                    self.config.version = issue.title.split(": ", 1)[1]
            if self.config.version:
                if self.config.version == "latest":
                    version = self.github.latest_release()
                    s.ok(f"Using latest release {version}")
                    return version

                self.require(
                    re.match(git.VERSION_REGEX, self.config.version) is not None,
                    f"Invalid version: {self.config.version} "
                    f"(expected: {git.VERSION_REGEX.pattern})",
                )
                s.ok(f"Accepting override version {self.config.version}")
                return self.config.version
            version = self.github.next_milestone().title
            if not self.config.production:
                # This is a prerelease, so we need to find the latest prerelease.
                rc = max(self.github.release_candidates(version), default=0)
                version = f"{version}-rc.{rc + 1}"
            self.require(re.match(git.VERSION_REGEX, version) is not None)
            s.ok(version)
        return version

    def stage_rename_issue(self, version: str) -> None:
        with stage.Stage("Rename issue", "Renaming the release tracking issue") as s:
            if not self.config.issue:
                s.ok("No issue to rename")
                return
            title = self.release_issue_title(version)
            issue = self.github.get_issue(self.config.issue)
            if issue.title == title:
                s.ok(f"Issue already named '{title}'")
                return
            self.github.rename_issue(self.config.issue, title)
            s.ok(f"Issue renamed to '{title}'")

    def stage_assign_milestone(self, version: str) -> None:
        with stage.Stage(
            "Assign milestone", "Assigning the release milestone to the issue"
        ) as s:
            if not self.config.issue:
                s.ok("No issue to assign")
                return
            if not self.config.production:
                v = git.parse_version(version)
                version = f"v{v.major}.{v.minor}.{v.patch}"
            m = self.github.milestone(version)
            self.github.assign_milestone(self.config.issue, m.number)
            s.ok(f"Issue assigned to milestone {m.title}")

    def stage_production_ready(self, version: str) -> None:
        """For production releases, check whether there are any more issues in the milestone."""
        with stage.Stage(
            "Production ready", "Checking if the release has any more open issues"
        ) as s:
            if self.config.production:
                m = self.github.next_milestone()
                issues = [
                    i
                    for i in self.github.open_milestone_issues(m.number)
                    if i.title != self.release_commit_message(version)
                    and i.number != self.config.issue
                ]
                if issues:
                    raise s.fail(
                        f"{len(issues)} issues are still open for "
                        f"{version}: {m.html_url}"
                    )
                s.ok(f"No open issues for {version}")
            else:
                s.ok("Release candidate; not checking milestone")

    def release_commit_message(self, version: str) -> str:
        return f"chore: Release {version}"

    def release_issue_title(self, version: str) -> str:
        return f"Release tracking issue: {version}"

    def stage_branch(self, version: str) -> None:
        with stage.Stage("Create release branch", "Creating a release branch") as s:
            release_branch = f"{BRANCH_PREFIX}/{version}"
            if (
                release_branch in self.git.branches()
                or release_branch in self.git.branches("origin")
            ):
                self.git.checkout(release_branch)
                if not self.config.rebase:
                    action = "skipping rebase"
                else:
                    rebased = self.git.last_commit_message(
                        release_branch
                    ) == self.release_commit_message(version)
                    if rebased:
                        if self.git.rebase(self.config.branch, commits=1):
                            action = f"rebased onto {self.config.branch}"
                        else:
                            action = f"already on {self.config.branch}"
                    else:
                        self.git.reset(self.config.branch)
                        action = f"reset to {self.config.branch}"
                s.ok(f"Branch '{release_branch}' already exists; {action}")
            else:
                self.git.create_branch(release_branch, self.config.branch)
                s.ok(
                    f"Branch '{release_branch}' created "
                    f"@ {self.git.branch_sha(release_branch)[:7]}"
                )
            self.require(
                self.git.current_branch() == release_branch, self.git.current_branch()
            )

    def stage_gitignore(self) -> None:
        """Ensure that third_party/ci-tools is in a .gitignore."""
        with stage.Stage("Gitignore", "Ensuring third_party/ci-tools is ignored") as s:
            if os.path.exists("third_party/.gitignore"):
                gitignore = "third_party/.gitignore"
                path = "/ci-tools\n"
            else:
                gitignore = ".gitignore"
                path = "/third_party/ci-tools\n"

            with open(gitignore, "r") as f:
                if path in f.readlines():
                    s.ok(f"'{path.strip()}' already in {gitignore}")
                    return

            with open(gitignore, "a") as f:
                f.write(path)
            self.git.add(gitignore)
            s.ok(f"Added '{path.strip()}' to {gitignore}")

    def stage_validate(self) -> None:
        validate_pr.main(
            validate_pr.Config(
                commit=not self.config.verify,
                release=self.config.production,
            )
        )

    def extract_issue_release_notes(self, body: str) -> str:
        """Extract the release notes from the issue body."""
        start = body.find("### Release notes")
        if start == -1:
            return ""
        end = body.find("### ", start + 1)
        return body[start:end].strip()

    def stage_release_notes(self, version: str) -> None:
        """Opens $EDITOR to edit the release notes in CHANGELOG.md."""
        with stage.Stage("Write release notes", "Opening editor") as s:
            if self.config.resume and changelog.has_release_notes(version):
                s.ok("Skipping")
            elif self.config.github_actions:
                m = self.github.next_milestone()
                tracking_issue = [
                    issue
                    for issue in self.github.open_milestone_issues(m.number)
                    if "toktok-releaser" in issue.assignees
                ]
                if not tracking_issue:
                    raise s.fail("No tracking issue found")
                if len(tracking_issue) > 1:
                    raise s.fail(
                        "Multiple tracking issues found: "
                        f"{', '.join(i.html_url for i in tracking_issue)}"
                    )
                issue = tracking_issue[0]
                notes = self.extract_issue_release_notes(issue.body)
                if not notes:
                    raise s.fail("No release notes found in issue body")
                changelog.set_release_notes(version, notes)
                self.git.add("CHANGELOG.md")
                s.ok(f"Release notes copied from {issue.html_url}")
            else:
                editor = os.getenv("EDITOR") or "vim"
                subprocess.run([editor, "CHANGELOG.md"], check=True)  # nosec
                self.git.add("CHANGELOG.md")
                s.ok()

    def stage_commit(self, version: str) -> None:
        with stage.Stage("Commit changes", "Committing changes") as s:
            release_notes = changelog.get_release_notes(version).notes + "\n"
            if self.git.is_clean():
                s.ok("No changes to commit")
                return

            changes = self.git.changed_files()
            self.git.commit(self.release_commit_message(version), release_notes)
            s.ok(str(changes))

    def stage_push(self) -> None:
        with stage.Stage("Push changes", "Pushing changes to origin") as s:
            release_branch = self.git.current_branch()
            if self.git.is_up_to_date(release_branch, self.config.upstream):
                s.ok("No changes to push")
                return

            if self.config.dryrun:
                s.ok("Dry run; not pushing changes")
            elif self.config.github_actions:
                sha = self.github.push_signed(
                    self.git.remote_slug(self.config.upstream),
                    self.git.branch_sha(release_branch),
                    self.config.main_branch,
                    release_branch,
                )
                self.git.fetch(self.config.upstream)
                self.git.reset(sha)
                s.ok(sha)
            else:
                self.git.push(
                    "origin", self.git.current_branch(), force=self.config.force
                )
                s.ok()

    def has_tarballs(self, version: str) -> bool:
        """Check if there are tarball assets for the given version."""
        assets = self.github.release_assets(version)
        return all(
            any(a.name == f"{version}.tar.{ext}" for a in assets)
            for ext in ("gz", "xz")
        )

    def get_pr_body(self, body: str) -> str:
        """Extract the Releaser section from the PR body."""
        start = body.find(RELEASER_START)
        end = body.find(RELEASER_END)
        if start == -1 or end == -1:
            return ""
        return body[start + len(RELEASER_START) : end].strip()

    def patch_pr_body(self, body: str, patch: str) -> str:
        """Patch the Releaser section in the PR body."""
        start = body.find(RELEASER_START)
        end = body.find(RELEASER_END)
        if start == -1 or end == -1:
            return f"{RELEASER_START}\n{patch}\n{RELEASER_END}\n{body}"
        return f"{body[:start]}{RELEASER_START}\n{patch}\n{RELEASER_END}\n{body[end + len(RELEASER_END):]}"

    def pr_patch(
        self, pr: github.PullRequest, title: str, body: str, milestone: int
    ) -> dict[str, str | int]:
        patch: dict[str, str | int] = {}
        if pr.state != "open":
            patch["state"] = "open"
        if pr.title != title:
            patch["title"] = title
        if pr.milestone != milestone:
            patch["milestone"] = milestone
        if self.get_pr_body(pr.body) != body:
            patch["body"] = self.patch_pr_body(pr.body, body)
        return patch

    def stage_pull_request(
        self,
        version: str,
    ) -> github.PullRequest | None:
        with stage.Stage(
            "Create pull request", "Creating a pull request on GitHub"
        ) as s:
            title = self.release_commit_message(version)
            body = changelog.get_release_notes(version).notes
            head = f"{self.git.owner('origin')}:{BRANCH_PREFIX}/{version}"
            base = self.config.main_branch
            milestone = self.github.next_milestone()
            existing_pr = self.github.find_pr_for_branch(head, base, "open")
            if self.config.dryrun:
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
                patch = self.pr_patch(existing_pr, title, body, milestone.number)
                if not patch:
                    s.ok(f"PR already exists: {existing_pr.html_url}")
                    return existing_pr

                self.github.change_pr(existing_pr.number, patch)
                if "milestone" in patch:
                    # Milestone is on issue, not PR.
                    self.github.change_issue(
                        existing_pr.number, {"milestone": patch["milestone"]}
                    )
                s.ok(f"Modified PR: {existing_pr.html_url}")
                return existing_pr

            s.progress(
                f"Creating PR: {title} ({head} -> {base}) "
                f"on milestone {milestone.number}"
            )
            pr = self.github.create_pr(
                title, self.patch_pr_body("", body), head, base, milestone.number
            )
            s.ok(pr.html_url)
            return pr

    def stage_restyled(self, version: str, parent: stage.Stage) -> None:
        if self.config.verify:
            # Can't do this on CI.
            return
        with stage.Stage("Restyled", "Applying restyled fixes", parent=parent) as s:
            subprocess.run(["hub-restyled"], check=True)  # nosec
            if self.git.is_clean():
                raise s.fail("Failed to apply restyled changes")
            self.git.add(".")
            self.stage_commit(version)
            self.stage_push()
            s.ok("Restyled changes applied")

    def get_head_pr(self, version: str) -> github.PullRequest | None:
        sha = self.git.find_commit_sha(self.release_commit_message(version))
        return self.github.find_pr(sha, self.config.main_branch)

    def await_head_pr(self, s: stage.Stage, version: str) -> github.PullRequest:
        """Wait for the PR to be synced with the head sha."""
        for _ in range(10):
            pr = self.get_head_pr(version)
            if pr:
                return pr
            s.progress(f"Waiting for release PR for {version}")
            stage.sleep(5)
        raise ValueError("Timeout waiting for PR to be created/updated")

    def stage_await_checks(self, version: str) -> None:
        with stage.Stage("Await checks", "Waiting for checks to pass") as s:
            for _ in range(120):  # 120 * 30s = 1 hour
                pr = self.await_head_pr(s, version)

                checks = self.github.checks(pr.head_sha)
                if not checks:
                    s.progress("Awaiting checks to start")
                    stage.sleep(10)
                    continue

                if self.config.verify:
                    # Remove "Verify release/signatures" check if we are
                    # running on CI (this is our own check).
                    del checks["Verify release/signatures"]

                completed = [c.name for c in checks.values() if c.status == "completed"]
                progress = [
                    c.name for c in checks.values() if c.status == "in_progress"
                ]
                success = [c.name for c in checks.values() if c.conclusion == "success"]
                failures = [
                    c.name for c in checks.values() if c.conclusion == "failure"
                ]
                neutral = [c.name for c in checks.values() if c.conclusion == "neutral"]

                if len(completed) == len(checks):
                    if failures:
                        raise s.fail(
                            f"{len(failures)} checks failed on "
                            f"{pr.html_url}: {', '.join(failures)}"
                        )
                    s.ok(f"All {len(completed)} checks passed")
                    return

                s.progress(
                    f"{len(success)} checks passed"
                    f", {len(neutral)} checks neutral"
                    f", {len(failures)} failed"
                    f", {len(progress)} in progress"
                )
                if (
                    "common / restyled" in checks
                    and checks["common / restyled"].conclusion == "failure"
                ):
                    self.stage_restyled(version, parent=s)

                stage.sleep(30)

            raise s.fail("Timeout waiting for checks to pass")

    def stage_ready_for_review(self, version: str) -> None:
        with stage.Stage("Ready for review", "Marking PR as ready for review") as s:
            pr = self.get_head_pr(version)
            if not pr:
                raise s.fail("PR not found")
            if pr.draft:
                self.github.mark_ready_for_review(pr.node_id)
                s.ok(f"PR {pr.number} is now ready for review")
            else:
                s.ok(f"PR {pr.number} is already ready for review")

    def stage_await_merged(self, version: str) -> None:
        """Wait for the PR to be merged by toktok-releaser."""
        with stage.Stage("Await merged", "Waiting for the PR to be merged") as s:
            for _ in range(120):  # 120 * 30s = 1 hour
                pr = self.get_head_pr(version)
                if not pr:
                    raise s.fail(f"PR not found for {version}")
                if pr.state == "closed":
                    if pr.merged:
                        s.ok(f"PR {pr.number} was merged")
                        self.git.checkout(self.config.main_branch)
                        self.git.pull(self.config.upstream)
                        return
                    raise s.fail(f"PR {pr.number} was closed without being merged")
                elif pr.state == "open":
                    s.progress(f"PR {pr.number} is still open")
                else:
                    s.progress(f"PR {pr.number} is {pr.state}")
                stage.sleep(30)
            raise s.fail("Timeout waiting for PR to be merged")

    def stage_await_master_build(self, version: str) -> None:
        """Wait for the master branch to be built."""
        with stage.Stage(
            "Await master build",
            f"Waiting for the {self.config.main_branch} branch to be built",
        ) as s:
            for _ in range(120):  # 120 * 30s = 1 hour
                head_sha = self.git.branch_sha(self.config.main_branch)
                builds = [
                    run
                    for run in self.github.action_runs(
                        self.config.main_branch, head_sha
                    )
                    if run.event != "issues"
                ]
                if not builds:
                    s.progress(
                        f"Waiting for builds to start for {self.config.main_branch}"
                    )
                    stage.sleep(10)
                    continue
                for build in builds:
                    if build.conclusion == "failure":
                        raise s.fail(f"Main branch failed to build: {build.html_url}")
                builds = [build for build in builds if build.status != "completed"]
                if not builds:
                    s.ok("Main branch built")
                    return
                s.progress(f"Main branch still building: {builds[0].html_url}")
                stage.sleep(30)
            raise s.fail(
                f"Timeout waiting for {self.config.main_branch} branch to be built"
            )

    def stage_tag(self, version: str) -> None:
        """Tag the release and push it to upstream."""
        with stage.Stage("Tag release", "Tagging the release") as s:
            release_notes = changelog.get_release_notes(version).notes + "\n"
            tag_exists = self.git.release_tag_exists(version)
            if tag_exists:
                s.progress(f"Tag {version} already exists")
            else:
                self.git.tag(
                    version, release_notes, sign=not self.config.github_actions
                )
                s.progress(f"Tagged {version}")

            if self.config.dryrun:
                s.ok("Dry run; not pushing tag")
                return

            if self.config.github_actions:
                if not tag_exists:
                    s.progress(f"Pushing tag {version} with GitHub API")
                    sha = self.github.tag(
                        self.git.remote_slug(self.config.upstream),
                        self.git.branch_sha(version),
                        version,
                        release_notes,
                    )
                else:
                    sha = self.git.branch_sha(version)

                self.github.create_release(
                    version, release_notes, prerelease=not self.config.production
                )
                self.github.clear_cache()
                self.git.fetch(self.config.upstream)
                s.ok(f"Tagged {version} @ {sha}")
            else:
                if not tag_exists:
                    self.git.push(
                        self.config.upstream, version, force=self.config.force
                    )
                    s.progress(f"Pushed tag {version} to {self.config.upstream}")

                self.github.create_release(
                    version, release_notes, prerelease=not self.config.production
                )
                self.github.clear_cache()
                s.ok()

    def stage_sign_tag(self, version: str) -> None:
        with stage.Stage("Sign tag", "Signing/verifying the release tag") as s:
            self.git.fetch(self.config.upstream)
            if self.git.tag_has_signature(version):
                if not self.git.verify_tag(version):
                    raise s.fail(f"Tag {version} signature cannot be verified")
                s.ok("Tag already signed")
                return
            if self.config.github_actions:
                s.ok("Asking user to sign the tag")
                raise self.assign_to_user(
                    s,
                    version,
                    task="Tagging",
                    action="sign the tag",
                    instruction=f"Please sign the tag locally: `python3 tools/sign_tag.py --tag {version}`",
                )
            sign_tag.main(
                sign_tag.Config(
                    tag=version,
                    upstream=self.config.upstream,
                    verify_only=False,
                    local_only=self.config.dryrun,
                )
            )
            s.ok("Tag signed")

    def stage_build_binaries(self, version: str) -> None:
        """Wait for GitHub Actions to build the binaries."""
        with stage.Stage("Build binaries", "Waiting for binaries to be built") as s:
            head_sha = self.git.branch_sha(version)
            for _ in range(6):  # 6 * 10s = 1 minute
                self.git.fetch(self.config.upstream)
                head_sha = self.git.branch_sha(version)
                builds = [run for run in self.github.action_runs(version, head_sha)]
                if builds:
                    break
                s.progress("Waiting for builds to start for " f"{version} @ {head_sha}")
                stage.sleep(10)
            else:
                if self.config.github_actions:
                    s.ok("No builds found; waiting for a human to sign the tag")
                    raise self.assign_to_user(
                        s,
                        version,
                        task="Tagging",
                        action="sign the tag",
                        instruction=f"No builds found; maybe the tag wasn't pushed? Please sign and push the tag: `python3 tools/sign_tag.py --tag {version}`",
                    )

            for _ in range(120):  # 120 * 30s = 1 hour
                builds = [run for run in self.github.action_runs(version, head_sha)]
                if not builds:
                    s.progress(
                        "Waiting for builds to start for " f"{version} @ {head_sha}"
                    )
                    stage.sleep(10)
                    continue
                for build in builds:
                    if build.conclusion == "failure":
                        raise s.fail(f"Binaries failed to build: {build.html_url}")
                todo = [build for build in builds if build.status != "completed"]
                if not todo:
                    s.ok(
                        f"Binaries built: {len(builds)} workflows completed "
                        f"for {head_sha}"
                    )
                    self.github.clear_cache()
                    return
                s.progress(f"Binaries still building: {builds[0].html_url}")
                stage.sleep(30)
            raise s.fail("Timeout waiting for binaries to be built")

    def stage_create_tarballs(self, version: str) -> None:
        with stage.Stage("Create tarballs", "Creating tarballs") as s:
            if self.has_tarballs(version):
                s.ok("Tarballs already created")
            else:
                project_name = self.github.repository_name()
                create_tarballs.main(
                    create_tarballs.Config(
                        upload=True, tag=version, project_name=project_name
                    )
                )
                s.ok("Tarballs created")

    def stage_sign_release_assets(self, version: str) -> None:
        with stage.Stage("Sign release assets", "Signing release assets") as s:
            if self.config.github_actions:
                assets = sign_release_assets.todo(version)
                if not assets:
                    s.ok("All release assets have been signed")
                    return
                s.progress(f"{len(assets)} release assets need signing")
                raise self.assign_to_user(
                    s,
                    version,
                    task="Binaries",
                    action="sign the assets",
                    instruction=f"Please sign the release assets: `python3 tools/sign_release_assets.py --tag {version}`",
                )

            sign_release_assets.main(
                sign_release_assets.Config(upload=True, tag=version), []
            )
            s.ok("Release assets signed")

    def stage_verify_release_assets(self, version: str) -> None:
        with stage.Stage("Verify release assets", "Verifying release assets") as s:
            count = verify_release_assets.main(
                verify_release_assets.Config(tag=version)
            )
            s.ok(f"Release assets verified: {count} assets")

    def stage_format_release_notes(self, version: str) -> None:
        with stage.Stage(
            "Format release notes", "Formatting release notes on GitHub release"
        ) as s:
            release_notes = changelog.get_release_notes(version)
            self.github.set_release_notes(
                version,
                release_notes.formatted(),
                prerelease=not self.config.production,
            )
            s.ok("Release notes formatted")

    def stage_publish_release(self, version: str) -> None:
        with stage.Stage("Publish release", "Publishing the release") as s:
            if self.github.release_is_published(version):
                s.ok("Release already published")
                return
            if self.config.github_actions:
                s.ok("Asking user to publish the release")
                release = self.github.release(version)
                url = release["html_url"]
                raise self.assign_to_user(
                    s,
                    version,
                    task="Publication",
                    action="publish the release",
                    instruction=f"All checks passed and assets signed. Please [publish the release]({url}) manually.",
                )
            s.ok("Not implemented yet")

    def stage_close_milestone(self, version: str) -> None:
        with stage.Stage("Close milestone", "Closing the release milestone") as s:
            if not self.config.production:
                s.ok("Not closing milestone for release candidate")
                return
            m = self.github.next_milestone()
            if m.title != version:
                raise s.fail(f"Milestone {m.title} is not the next milestone")
            self.github.close_milestone(m.number)
            s.ok(f"Milestone {m.title} closed")

    def stage_close_issue(self) -> None:
        with stage.Stage("Close issue", "Closing the release tracking issue") as s:
            if not self.config.issue:
                s.ok("No issue to close")
                return
            issue = self.github.get_issue(self.config.issue)
            if issue.state == "closed":
                s.ok("Issue already closed")
                return
            self.github.close_issue(self.config.issue)
            s.ok(f"Issue {self.config.issue} closed")

    def run_stages(self) -> None:
        self.require(self.git.current_branch() == self.config.branch)
        self.require(self.git.is_clean())

        self.stage_init()

        version = self.stage_version()
        self.stage_rename_issue(version)
        self.stage_assign_milestone(version)
        self.stage_production_ready(version)

        self.update_dashboard(version)

        if self.release_commit_message(version) not in self.git.log(
            self.config.main_branch
        ):
            self.stage_branch(version)
            self.stage_gitignore()
            self.stage_validate()
            self.stage_release_notes(version)
            self.stage_commit(version)
            self.stage_push()
            self.stage_pull_request(version)
            self.update_dashboard(version)
            if not self.config.dryrun:
                self.stage_await_checks(version)
                if self.config.verify:
                    return
                self.stage_ready_for_review(version)

            if self.config.dryrun:
                print("Dry run: stopping after preparation")
                return
        else:
            print(
                f"Release branch {BRANCH_PREFIX}/{version} already merged.", flush=True
            )
        self.stage_await_merged(version)
        self.update_dashboard(version)
        self.stage_await_master_build(version)
        self.stage_tag(version)
        self.stage_sign_tag(version)
        self.update_dashboard(version)
        self.stage_build_binaries(version)
        self.stage_create_tarballs(version)
        self.stage_sign_release_assets(version)
        self.update_dashboard(version)
        self.stage_verify_release_assets(version)
        self.stage_format_release_notes(version)
        self.stage_publish_release(version)
        self.update_dashboard(version)
        self.stage_close_milestone(version)
        self.stage_close_issue()


def main(config: Config) -> None:
    # chdir into the root of the repository.
    os.chdir(git.root())
    # We need auth to get the draft release etc.
    print("Building release as GitHub user", github.actor())

    git_prov = git.DEFAULT_GIT
    github_prov = github.DEFAULT_GITHUB

    try:
        # Stash any local changes for the user to later resume working on.
        with git.Stash(prov=git_prov):
            # We need to be on the main branch to create a release, but we
            # want to return to the original branch afterwards.
            with git.Checkout(config.branch, prov=git_prov):
                # Undo any partial changes if the script is aborted.
                with git.ResetOnExit(prov=git_prov):
                    releaser = Releaser(config, git_prov, github_prov)
                    releaser.run_stages()
    except stage.UserAbort as e:
        print(e.message)
        return


if __name__ == "__main__":
    main(parse_args())
