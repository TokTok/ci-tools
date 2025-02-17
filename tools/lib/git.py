# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import pathlib
import re
import subprocess  # nosec
import unittest
from dataclasses import dataclass
from functools import cache as memoize
from typing import Any
from typing import Optional

from lib import types

VERSION_REGEX = re.compile(r"v\d+\.\d+(?:\.\d+)?(?:-rc\.\d+)?")
RELEASE_BRANCH_PREFIX = "release"
RELEASE_BRANCH_REGEX = re.compile(
    f"{RELEASE_BRANCH_PREFIX}/{VERSION_REGEX.pattern}")


@dataclass
class Version:
    major: int
    minor: int
    patch: int
    rc: Optional[int]

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}" + (
            f"-rc.{self.rc}" if self.rc is not None else "")

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


class TestParseVersion(unittest.TestCase):

    def test_parse_version(self) -> None:
        self.assertEqual(parse_version("v1.2.3"), Version(1, 2, 3, None))
        self.assertEqual(parse_version("v1.2.3-rc.1"), Version(1, 2, 3, 1))

    def test_comparison(self) -> None:
        self.assertLess(parse_version("v1.2.3"), parse_version("v1.2.4"))
        self.assertLess(parse_version("v1.2.3"), parse_version("v1.3.0"))
        self.assertLess(parse_version("v1.2.3"), parse_version("v2.0.0"))
        self.assertLess(parse_version("v1.2.3-rc.1"),
                        parse_version("v1.2.3-rc.2"))
        self.assertLess(parse_version("v1.2.3-rc.1"), parse_version("v1.2.3"))
        self.assertGreater(parse_version("v1.2.3"), parse_version("v1.2.2"))
        self.assertGreater(parse_version("v1.2.3"),
                           parse_version("v1.2.3-rc.1"))
        self.assertEqual(parse_version("v1.2.3"), parse_version("v1.2.3"))
        self.assertEqual(parse_version("v1.2.3-rc.1"),
                         parse_version("v1.2.3-rc.1"))
        self.assertNotEqual(parse_version("v1.2.3"), parse_version("v1.2.4"))


class Stash:

    def __init__(self) -> None:
        self.stashed = False

    def __enter__(self) -> None:
        if diff_exitcode():
            print("Stashing changes.")
            self.stashed = True
            subprocess.check_call(  # nosec
                [
                    "git",
                    "stash",
                    "--quiet",
                    "--include-untracked",
                ])

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.stashed:
            print("Restoring stashed changes.")
            subprocess.check_call(  # nosec
                [
                    "git",
                    "stash",
                    "pop",
                    "--quiet",
                ])


class Checkout:

    def __init__(self, branch: str) -> None:
        self.branch = branch
        self.old_branch = current_branch()

    def __enter__(self) -> None:
        if self.branch != current_branch():
            print(f"Checking out {self.branch} (from {self.old_branch}).")
            subprocess.check_call(  # nosec
                [
                    "git",
                    "checkout",
                    "--quiet",
                    self.branch,
                ])

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.old_branch != current_branch():
            print(f"Moving back to {self.old_branch}.")
            subprocess.check_call(  # nosec
                [
                    "git",
                    "checkout",
                    "--quiet",
                    self.old_branch,
                ])


class ResetOnExit:

    def __init__(self) -> None:
        self.branch = current_branch()

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        subprocess.check_call(  # nosec
            [
                "git",
                "reset",
                "--quiet",
                "--hard",
            ])


@memoize
def root() -> str:
    """Get the root directory of the git repository."""
    return (subprocess.check_output(  # nosec
        [
            "git",
            "rev-parse",
            "--show-toplevel",
        ]).strip().decode("utf-8"))


def root_dir() -> pathlib.Path:
    """Returns the top level source directory as Path object."""
    return pathlib.Path(root())


def fetch(*remotes: str) -> None:
    """Fetch tags and branches from a remote.

    Making sure our knowledge of the remote state is up-to-date. Fetches all
    branches, tags, and prunes stale references. Overwrites local tags if they
    have been updated on the remote.
    """
    subprocess.check_call(  # nosec
        [
            "git",
            "fetch",
            "--quiet",
            "--tags",
            "--prune",
            "--force",
            "--multiple",
            *remotes,
        ])


def pull(remote: str) -> None:
    """Pull changes from the current branch and remote."""
    subprocess.check_call(  # nosec
        [
            "git",
            "pull",
            "--rebase",
            "--quiet",
            remote,
            current_branch(),
        ])


def remote_slug(remote: str) -> types.RepoSlug:
    """Get the GitHub slug of a remote."""
    url = (
        subprocess.check_output(  # nosec
            [
                "git",
                "remote",
                "get-url",
                remote,
            ]).strip().decode("utf-8"))
    match = re.search(r"[:/]([^/]+)/([^./]+)(?:\.git)?$", url)
    if not match:
        raise ValueError(f"Could not parse remote URL: {url}")
    return types.RepoSlug(match.group(1), match.group(2))


def owner(remote: str) -> str:
    """Get the owner of a remote."""
    return remote_slug(remote).owner


def remotes() -> list[str]:
    """Return a list of remote names (e.g. origin, upstream)."""
    return subprocess.check_output(  # nosec
        ["git", "remote"],
        universal_newlines=True,
    ).splitlines()


def branch_sha(branch: str) -> str:
    """Get the SHA of a branch."""
    return (subprocess.check_output(  # nosec
        [
            "git",
            "rev-list",
            "--max-count=1",
            branch,
        ]).strip().decode("utf-8"))


def branches(remote: Optional[str] = None) -> list[str]:
    """Get a list of branches, optionally from a remote.

    If remote is None, return local branches.
    """
    if remote is not None and remote not in remotes():
        raise ValueError(f"Remote {remote} does not exist.")
    bs = subprocess.check_output(  # nosec
        [
            "git",
            "branch",
            "--list",
            "--no-column",
            "--format=%(refname:short)",
        ] + ([] if remote is None else ["--remotes"]),
        universal_newlines=True,
    ).splitlines()
    if remote is None:
        return bs
    return [b.split("/", 1)[1] for b in bs if b.startswith(f"{remote}/")]


def current_branch() -> str:
    """Get the current branch name."""
    return (subprocess.check_output(  # nosec
        [
            "git",
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
        ]).strip().decode("utf-8"))


def release_tags(with_rc: bool = True) -> list[str]:
    tags = subprocess.check_output(["git", "tag", "--merged"])  # nosec
    return sorted(
        (tag for tag in tags.decode("utf-8").splitlines()
         if re.match(VERSION_REGEX, tag) and (with_rc or "-rc." not in tag)),
        reverse=True,
        key=parse_version,
    )


def release_tag_exists(tag: str) -> bool:
    """Check if a tag exists."""
    return tag in release_tags()


def tag(tag: str, message: str, sign: bool) -> None:
    """Create a signed tag with a message."""
    subprocess.check_call(  # nosec
        [
            "git",
            "tag",
            *(["--sign"] if sign else []),
            "--annotate",
            "--message",
            message,
            tag,
        ])


def release_branches() -> list[str]:
    """Get a list of release branches."""
    return [b for b in branches() if re.match(RELEASE_BRANCH_REGEX, b)]


def diff_exitcode(*args: str) -> bool:
    """Check if there are any changes in the git working directory."""
    return (subprocess.run(  # nosec
        [
            "git",
            "diff",
            "--quiet",
            "--exit-code",
            *args,
        ],
        check=False,
    ).returncode != 0)


def is_clean() -> bool:
    """Check if the git working directory is clean.

    No pending or staged changes.
    """
    return not diff_exitcode() and not diff_exitcode("--cached")


def changed_files() -> list[str]:
    """Get a list of changed files."""
    return subprocess.check_output(  # nosec
        [
            "git",
            "diff",
            "--name-only",
            "HEAD",
        ],
        universal_newlines=True,
    ).splitlines()


def current_tag() -> str:
    """Get the most recent tag."""
    return (subprocess.check_output(  # nosec
        [
            "git",
            "describe",
            "--tags",
            "--abbrev=0",
            "--match",
            "v*",
        ]).decode("utf-8").strip())


def tag_has_signature(tag: str) -> bool:
    """Check if a tag has a signature."""
    return b"-----BEGIN PGP SIGNATURE-----" in subprocess.check_output(  # nosec
        [
            "git",
            "cat-file",
            "tag",
            tag,
        ])


def verify_tag(tag: str) -> bool:
    """Verify the signature of a tag."""
    return (subprocess.run(  # nosec
        [
            "git",
            "verify-tag",
            "--verbose",
            tag,
        ],
        check=False,
    ).returncode == 0)


def sign_tag(tag: str) -> None:
    """Sign a tag with its original message."""
    subprocess.check_call(  # nosec
        [
            "git",
            "tag",
            "--sign",
            "--force",
            tag,
            f"{tag}^{{}}",
        ])


def push_tag(tag: str, remote: str) -> None:
    """Push a tag to a remote."""
    subprocess.check_call(  # nosec
        [
            "git",
            "push",
            "--quiet",
            "--force",
            remote,
            tag,
        ])


def checkout(branch: str) -> None:
    """Checkout a branch."""
    subprocess.check_call(  # nosec
        [
            "git",
            "checkout",
            "--quiet",
            branch,
        ])


def revert(*files: str) -> None:
    """Checkout files."""
    branch = current_branch()
    subprocess.check_call(  # nosec
        [
            "git",
            "checkout",
            "--quiet",
            branch,
            "--",
            *files,
        ])


def add(*files: str) -> None:
    """Add files to the index."""
    subprocess.check_call(  # nosec
        [
            "git",
            "add",
            *files,
        ])


def reset(branch: str) -> None:
    """Reset a branch to a specific commit."""
    subprocess.check_call(  # nosec
        [
            "git",
            "reset",
            "--quiet",
            "--hard",
            branch,
        ])


def rebase(onto: str, commits: int = 0) -> bool:
    """Rebase the current branch onto another branch.

    If commits is not 0, rebase only the last n commits.

    Returns True if a rebase was performed.
    """
    old_sha = branch_sha("HEAD")
    if not commits:
        subprocess.check_call(  # nosec
            [
                "git",
                "rebase",
                "--quiet",
                onto,
            ])
    else:
        branch = current_branch()
        subprocess.check_call(  # nosec
            [
                "git",
                "rebase",
                "--quiet",
                "--onto",
                onto,
                f"HEAD~{commits}",
            ])
        new_sha = branch_sha("HEAD")
        checkout(branch)
        reset(new_sha)
    return old_sha != branch_sha("HEAD")


def create_branch(branch: str, base: str) -> None:
    """Create a branch from a base branch."""
    subprocess.check_call(  # nosec
        [
            "git",
            "checkout",
            "--quiet",
            "-b",
            branch,
            base,
        ])


def push(remote: str, branch: str, force: bool = False) -> None:
    """Push the current branch to a remote."""
    force_flag = ["--force"] if force else []
    subprocess.check_call(  # nosec
        [
            "git",
            "push",
            "--quiet",
            *force_flag,
            "--set-upstream",
            remote,
            branch,
        ])


def list_changed_files() -> list[str]:
    """List all files that have been changed."""
    return subprocess.check_output(  # nosec
        [
            "git",
            "diff",
            "--name-only",
        ],
        universal_newlines=True,
    ).splitlines()


def log(branch: str, count: int = 100) -> list[str]:
    """Get the last n commit messages."""
    return [
        line.split(" ", 1)[1].strip()
        for line in subprocess.check_output(  # nosec
            [
                "git",
                "log",
                "--oneline",
                "--no-decorate",
                f"--max-count={count}",
                branch,
            ],
            universal_newlines=True,
        ).splitlines()
    ]


def find_commit_sha(message: str) -> str:
    """Find the commit SHA of a commit message."""
    return (subprocess.check_output(  # nosec
        [
            "git",
            "log",
            "--format=%H",
            "--grep",
            message,
            "-1",
        ]).strip().decode("utf-8"))


def last_commit_message(branch: str) -> str:
    """Get the last commit message."""
    return log(branch, 1)[0]


def commit(title: str, body: str) -> None:
    """Commit changes.

    If the commit message is the same as the last commit, amend it.
    """
    amend = ["--amend"] if last_commit_message(
        current_branch()) == title else []
    subprocess.check_call(  # nosec
        [
            "git",
            "commit",
            "--quiet",
            *amend,
            "--message",
            title,
            "--message",
            body,
        ])


def files_changed(commit: str) -> list[str]:
    """Get a list of files changed in a commit."""
    return subprocess.check_output(  # nosec
        [
            "git",
            "diff",
            "--name-only",
            f"{commit}^",
        ],
        universal_newlines=True,
    ).splitlines()


def commit_message(commit_sha: str) -> str:
    """Get the commit message of a commit."""
    return subprocess.check_output(  # nosec
        [
            "git",
            "show",
            "--quiet",
            "--format=%B",
            commit_sha,
        ],
        universal_newlines=True,
    )


def is_up_to_date(branch: str, remote: str) -> bool:
    """Check if a branch sha is equal to its remote counterpart."""
    return branch in branches(remote) and branch_sha(branch) == branch_sha(
        f"{remote}/{branch}")
