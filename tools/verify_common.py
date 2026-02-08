#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import os
import shutil
import subprocess  # nosec
import sys
import tempfile
from typing import Any

from lib import git, github


class Workspace:
    def __init__(self, repo_name: str, tag: str) -> None:
        self.repo_name = repo_name
        self.tag = tag
        self.root: str = ""
        self.temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self.ci_tools_path = git.root()

    def __enter__(self) -> "Workspace":
        self.temp_dir = tempfile.TemporaryDirectory(prefix=f"verify-{self.repo_name}-")
        self.root = self.temp_dir.name
        print(f"Created temporary workspace: {self.root}", file=sys.stderr)

        # 1. Clone the target repository
        repo_url = f"https://github.com/TokTok/{self.repo_name}.git"
        print(f"Cloning {self.repo_name} at tag {self.tag}...", file=sys.stderr)
        subprocess.run(  # nosec
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                self.tag,
                repo_url,
                self.root,
            ],
            check=True,
            capture_output=True,
        )

        # 2. Setup third_party/ci-tools
        # We want to use the current ci-tools code for verification.
        # We must COPY rather than symlink, otherwise Docker cannot see it.
        tp_dir = os.path.join(self.root, "third_party")
        os.makedirs(tp_dir, exist_ok=True)
        ci_tools_dst = os.path.join(tp_dir, "ci-tools")
        print("Copying ci-tools into workspace...", file=sys.stderr)

        # We ignore the temp directories and git to keep it fast
        shutil.copytree(
            self.ci_tools_path,
            ci_tools_dst,
            ignore=shutil.ignore_patterns(
                ".git", "third_party", "__pycache__", "*.AppImage", "*.flatpak"
            ),
            dirs_exist_ok=True,
        )

        # 3. Setup TokTok/dockerfiles
        dockerfiles_dir = os.path.join(tp_dir, "dockerfiles")
        print("Cloning TokTok/dockerfiles...", file=sys.stderr)
        subprocess.run(  # nosec
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "https://github.com/TokTok/dockerfiles.git",
                dockerfiles_dir,
            ],
            check=True,
            capture_output=True,
        )

        # 4. Copy docker-compose.yml to root
        src_compose = os.path.join(dockerfiles_dir, "docker-compose.yml")
        dst_compose = os.path.join(self.root, "docker-compose.yml")
        shutil.copy2(src_compose, dst_compose)

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self.temp_dir:
            print(f"Cleaning up workspace: {self.root}", file=sys.stderr)
            self.temp_dir.cleanup()

    def run_docker(
        self, service: str, command: list[str], env: dict[str, str] | None = None
    ) -> None:
        """Run a command via docker compose in the workspace."""
        cmd = ["docker", "compose", "run", "--rm"]
        if env:
            for k, v in env.items():
                cmd.extend(["-e", f"{k}={v}"])
        cmd.extend([service] + command)

        process = subprocess.run(  # nosec
            cmd, cwd=self.root, capture_output=True, text=True
        )

        if process.returncode != 0:
            print(f"Error running docker command in {service}:", file=sys.stderr)
            print(process.stdout, file=sys.stderr)
            print(process.stderr, file=sys.stderr)
            process.check_returncode()


def get_default_repo() -> str:
    try:
        return github.repository_name()
    except Exception:
        return "ci-tools"


def detect_project_name(root_dir: str) -> str | None:
    """Detect the project name from CMakeLists.txt, mirroring CI logic."""
    cmake_path = os.path.join(root_dir, "CMakeLists.txt")
    if not os.path.exists(cmake_path):
        return None

    # Mirroring: pcregrep -M -o1 'project\(\s*(\S+)' CMakeLists.txt
    import re

    with open(cmake_path, "r") as f:
        content = f.read()
        match = re.search(r"project\(\s*(\S+)", content, re.MULTILINE)
        if match:
            # Strip potential quotes or closing parenthesis
            name = match.group(1).split(")")[0].strip("\"'")
            return name
    return None
