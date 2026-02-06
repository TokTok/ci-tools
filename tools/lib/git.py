# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2026 The TokTok team
import pathlib
import re
import subprocess  # nosec
import unittest
from dataclasses import dataclass
from typing import Any

from lib import types

VERSION_REGEX = re.compile(r"v\d+\.\d+(?:\.\d+)?(?:-rc\.\d+)?")
RELEASE_BRANCH_PREFIX = "release"
RELEASE_BRANCH_REGEX = re.compile(f"{RELEASE_BRANCH_PREFIX}/{VERSION_REGEX.pattern}")


@dataclass
class Version:
    major: int
    minor: int
    patch: int
    rc: int | None

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}" + (
            f"-rc.{self.rc}" if self.rc is not None else ""
        )

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        if self.rc is None:
            return False
        if other.rc is None:
            return True
        return self.rc < other.rc


def parse_version(version: str) -> Version:
    match = re.match(r"v(\d+)\.(\d+)(?:\.(\d+))?(?:-rc\.(\d+))?", version)
    if not match:
        raise ValueError(f"Could not parse version: {version}")
    return Version(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)) if match.group(3) else 0,
        rc=int(match.group(4)) if match.group(4) else None,
    )


class Git:
    """A provider for Git commands."""

    def __init__(self) -> None:
        self._root_cache: str | None = None

    def _run_output(self, args: list[str]) -> str:
        return subprocess.check_output(["git"] + args).strip().decode("utf-8")

    def _run_call(self, args: list[str]) -> None:
        subprocess.check_call(["git"] + args)  # nosec

    def _run_status(self, args: list[str]) -> int:
        return subprocess.run(["git"] + args, check=False).returncode  # nosec

    def root(self) -> str:
        """Get the root directory of the git repository."""
        if self._root_cache is None:
            self._root_cache = self._run_output(["rev-parse", "--show-toplevel"])
        return self._root_cache

    def root_dir(self) -> pathlib.Path:
        """Returns the top level source directory as Path object."""
        return pathlib.Path(self.root())

    def fetch(self, *remotes: str) -> None:
        """Fetch tags and branches from a remote."""
        self._run_call(
            [
                "fetch",
                "--quiet",
                "--tags",
                "--prune",
                "--force",
                "--multiple",
                *remotes,
            ]
        )

    def pull(self, remote: str) -> None:
        """Pull changes from the current branch and remote."""
        self._run_call(
            [
                "pull",
                "--rebase",
                "--quiet",
                remote,
                self.current_branch(),
            ]
        )

    def remote_slug(self, remote: str) -> types.RepoSlug:
        """Get the GitHub slug of a remote."""
        url = self._run_output(["remote", "get-url", remote])
        match = re.search(r"[:/]([^/]+)/([^./]+)(?:\.git)?$", url)
        if not match:
            raise ValueError(f"Could not parse remote URL: {url}")
        return types.RepoSlug(match.group(1), match.group(2))

    def owner(self, remote: str) -> str:
        """Get the owner of a remote."""
        return self.remote_slug(remote).owner

    def remotes(self) -> list[str]:
        """Return a list of remote names (e.g. origin, upstream)."""
        return self._run_output(["remote"]).splitlines()

    def branch_sha(self, branch: str) -> str:
        """Get the SHA of a branch."""
        return self._run_output(["rev-list", "--max-count=1", branch])

    def branches(self, remote: str | None = None) -> list[str]:
        """Get a list of branches, optionally from a remote."""
        if remote is not None and remote not in self.remotes():
            raise ValueError(f"Remote {remote} does not exist.")
        args = [
            "branch",
            "--list",
            "--no-column",
            "--format=%(refname:short)",
        ]
        if remote is not None:
            args.append("--remotes")

        bs = self._run_output(args).splitlines()
        if remote is None:
            return bs
        return [b.split("/", 1)[1] for b in bs if b.startswith(f"{remote}/")]

    def current_branch(self) -> str:
        """Get the current branch name."""
        return self._run_output(["rev-parse", "--abbrev-ref", "HEAD"])

    def release_tags(self, with_rc: bool = True) -> list[str]:
        tags = self._run_output(["tag", "--merged"]).splitlines()
        all_tags = sorted(
            (tag for tag in tags if re.match(VERSION_REGEX, tag)),
            reverse=True,
            key=parse_version,
        )

        if not with_rc:
            return [t for t in all_tags if "-rc." not in t]

        prod_versions = {t for t in all_tags if "-rc." not in t}
        return [
            t
            for t in all_tags
            if "-rc." not in t or t.split("-rc.")[0] not in prod_versions
        ]

    def release_tag_exists(self, tag: str) -> bool:
        """Check if a tag exists."""
        return tag in self.release_tags()

    def tag(self, tag: str, message: str, sign: bool) -> None:
        """Create a signed tag with a message."""
        args = ["tag"]
        if sign:
            args.append("--sign")
        args.extend(["--annotate", "--message", message, tag])
        self._run_call(args)

    def release_branches(self) -> list[str]:
        """Get a list of release branches."""
        return [b for b in self.branches() if re.match(RELEASE_BRANCH_REGEX, b)]

    def diff_exitcode(self, *args: str) -> bool:
        """Check if there are any changes in the git working directory."""
        return self._run_status(["diff", "--quiet", "--exit-code", *args]) != 0

    def is_clean(self) -> bool:
        """Check if the git working directory is clean."""
        return not self.diff_exitcode() and not self.diff_exitcode("--cached")

    def changed_files(self) -> list[str]:
        """Get a list of changed files."""
        return self._run_output(["diff", "--name-only", "HEAD"]).splitlines()

    def current_tag(self) -> str:
        """Get the most recent tag."""
        return self._run_output(["describe", "--tags", "--abbrev=0", "--match", "v*"])

    def tag_has_signature(self, tag: str) -> bool:
        """Check if a tag has a signature."""
        return "-----BEGIN PGP SIGNATURE-----" in self._run_output(
            ["cat-file", "tag", tag]
        )

    def verify_tag(self, tag: str) -> bool:
        """Verify the signature of a tag."""
        return self._run_status(["verify-tag", "--verbose", tag]) == 0

    def sign_tag(self, tag: str) -> None:
        """Sign a tag with its original message."""
        self._run_call(["tag", "--sign", "--force", tag, f"{tag}^{{}}"])

    def push_tag(self, tag: str, remote: str) -> None:
        """Push a tag to a remote."""
        self._run_call(["push", "--quiet", "--force", remote, tag])

    def checkout(self, branch: str) -> None:
        """Checkout a branch."""
        self._run_call(["checkout", "--quiet", branch])

    def revert(self, *files: str) -> None:
        """Checkout files."""
        branch = self.current_branch()
        self._run_call(["checkout", "--quiet", branch, "--", *files])

    def add(self, *files: str) -> None:
        """Add files to the index."""
        self._run_call(["add", *files])

    def reset(self, branch: str) -> None:
        """Reset a branch to a specific commit."""
        self._run_call(["reset", "--quiet", "--hard", branch])

    def rebase(self, onto: str, commits: int = 0) -> bool:
        """Rebase the current branch onto another branch."""
        old_sha = self.branch_sha("HEAD")
        if not commits:
            self._run_call(["rebase", "--quiet", onto])
        else:
            branch = self.current_branch()
            self._run_call(["rebase", "--quiet", "--onto", onto, f"HEAD~{commits}"])
            new_sha = self.branch_sha("HEAD")
            self.checkout(branch)
            self.reset(new_sha)
        return old_sha != self.branch_sha("HEAD")

    def create_branch(self, branch: str, base: str) -> None:
        """Create a branch from a base branch."""
        self._run_call(["checkout", "--quiet", "-b", branch, base])

    def push(self, remote: str, branch: str, force: bool = False) -> None:
        """Push the current branch to a remote."""
        args = ["push", "--quiet"]
        if force:
            args.append("--force")
        args.extend(["--set-upstream", remote, branch])
        self._run_call(args)

    def list_changed_files(self) -> list[str]:
        """List all files that have been changed."""
        return self._run_output(["diff", "--name-only"]).splitlines()

    def log(self, branch: str, count: int = 100) -> list[str]:
        """Get the last n commit messages."""
        lines = self._run_output(
            [
                "log",
                "--oneline",
                "--no-decorate",
                f"--max-count={count}",
                branch,
            ]
        ).splitlines()
        return [line.split(" ", 1)[1].strip() for line in lines]

    def find_commit_sha(self, message: str) -> str:
        """Find the commit SHA of a commit message."""
        return self._run_output(["log", "--format=%H", "--grep", message, "-1"])

    def last_commit_message(self, branch: str) -> str:
        """Get the last commit message."""
        return self.log(branch, 1)[0]

    def commit(self, title: str, body: str) -> None:
        """Commit changes."""
        args = ["commit", "--quiet"]
        if self.last_commit_message(self.current_branch()) == title:
            args.append("--amend")
        args.extend(["--message", title, "--message", body])
        self._run_call(args)

    def files_changed(self, commit: str) -> list[str]:
        """Get a list of files changed in a commit."""
        return self._run_output(["diff", "--name-only", f"{commit}^"]).splitlines()

    def commit_message(self, commit_sha: str) -> str:
        """Get the commit message of a commit."""
        return self._run_output(["show", "--quiet", "--format=%B", commit_sha])

    def is_up_to_date(self, branch: str, remote: str) -> bool:
        """Check if a branch sha is equal to its remote counterpart."""
        return branch in self.branches(remote) and self.branch_sha(
            branch
        ) == self.branch_sha(f"{remote}/{branch}")


DEFAULT_GIT = Git()


class Stash:
    def __init__(self, prov: Git = DEFAULT_GIT) -> None:
        self.prov = prov
        self.stashed = False

    def __enter__(self) -> None:
        if self.prov.diff_exitcode():
            print("Stashing changes.")
            self.stashed = True
            self.prov._run_call(["stash", "--quiet", "--include-untracked"])

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.stashed:
            print("Restoring stashed changes.")
            self.prov._run_call(["stash", "pop", "--quiet"])


class Checkout:
    def __init__(self, branch: str, prov: Git = DEFAULT_GIT) -> None:
        self.branch = branch
        self.prov = prov
        self.old_branch = prov.current_branch()

    def __enter__(self) -> None:
        if self.branch != self.prov.current_branch():
            print(f"Checking out {self.branch} (from {self.old_branch}).")
            self.prov.checkout(self.branch)

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.old_branch != self.prov.current_branch():
            print(f"Moving back to {self.old_branch}.")
            self.prov.checkout(self.old_branch)


class ResetOnExit:
    def __init__(self, prov: Git = DEFAULT_GIT) -> None:
        self.prov = prov

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.prov.reset(self.prov.current_branch())


def root() -> str:
    return DEFAULT_GIT.root()


def root_dir() -> pathlib.Path:
    return DEFAULT_GIT.root_dir()


def fetch(*remotes: str) -> None:
    DEFAULT_GIT.fetch(*remotes)


def pull(remote: str) -> None:
    DEFAULT_GIT.pull(remote)


def remote_slug(remote: str) -> types.RepoSlug:
    return DEFAULT_GIT.remote_slug(remote)


def owner(remote: str) -> str:
    return DEFAULT_GIT.owner(remote)


def remotes() -> list[str]:
    return DEFAULT_GIT.remotes()


def branch_sha(branch: str) -> str:
    return DEFAULT_GIT.branch_sha(branch)


def branches(remote: str | None = None) -> list[str]:
    return DEFAULT_GIT.branches(remote)


def current_branch() -> str:
    return DEFAULT_GIT.current_branch()


def release_tags(with_rc: bool = True) -> list[str]:
    return DEFAULT_GIT.release_tags(with_rc)


def release_tag_exists(tag: str) -> bool:
    return DEFAULT_GIT.release_tag_exists(tag)


def tag(tag: str, message: str, sign: bool) -> None:
    DEFAULT_GIT.tag(tag, message, sign)


def release_branches() -> list[str]:
    return DEFAULT_GIT.release_branches()


def diff_exitcode(*args: str) -> bool:
    return DEFAULT_GIT.diff_exitcode(*args)


def is_clean() -> bool:
    return DEFAULT_GIT.is_clean()


def changed_files() -> list[str]:
    return DEFAULT_GIT.changed_files()


def current_tag() -> str:
    return DEFAULT_GIT.current_tag()


def tag_has_signature(tag: str) -> bool:
    return DEFAULT_GIT.tag_has_signature(tag)


def verify_tag(tag: str) -> bool:
    return DEFAULT_GIT.verify_tag(tag)


def sign_tag(tag: str) -> None:
    DEFAULT_GIT.sign_tag(tag)


def push_tag(tag: str, remote: str) -> None:
    DEFAULT_GIT.push_tag(tag, remote)


def checkout(branch: str) -> None:
    DEFAULT_GIT.checkout(branch)


def revert(*files: str) -> None:
    DEFAULT_GIT.revert(*files)


def add(*files: str) -> None:
    DEFAULT_GIT.add(*files)


def reset(branch: str) -> None:
    DEFAULT_GIT.reset(branch)


def rebase(onto: str, commits: int = 0) -> bool:
    return DEFAULT_GIT.rebase(onto, commits)


def create_branch(branch: str, base: str) -> None:
    DEFAULT_GIT.create_branch(branch, base)


def push(remote: str, branch: str, force: bool = False) -> None:
    DEFAULT_GIT.push(remote, branch, force)


def list_changed_files() -> list[str]:
    return DEFAULT_GIT.list_changed_files()


def log(branch: str, count: int = 100) -> list[str]:
    return DEFAULT_GIT.log(branch, count)


def find_commit_sha(message: str) -> str:
    return DEFAULT_GIT.find_commit_sha(message)


def last_commit_message(branch: str) -> str:
    return DEFAULT_GIT.last_commit_message(branch)


def commit(title: str, body: str) -> None:
    DEFAULT_GIT.commit(title, body)


def files_changed(commit: str) -> list[str]:
    return DEFAULT_GIT.files_changed(commit)


def commit_message(commit_sha: str) -> str:
    return DEFAULT_GIT.commit_message(commit_sha)


def is_up_to_date(branch: str, remote: str) -> bool:
    return DEFAULT_GIT.is_up_to_date(branch, remote)
