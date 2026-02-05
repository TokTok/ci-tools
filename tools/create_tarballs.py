#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import argparse
import os
import subprocess  # nosec
import tempfile
from dataclasses import dataclass

from lib import git, github


@dataclass
class Config:
    upload: bool
    tag: str
    project_name: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Create and optionally upload source tarballs for the project.
    """)
    parser.add_argument(
        "--upload",
        action=argparse.BooleanOptionalAction,
        help="Upload tarballs to GitHub",
        default=False,
    )
    parser.add_argument(
        "--tag",
        help="Tag to create tarballs for",
        default=git.current_tag(),
    )
    parser.add_argument(
        "--project-name",
        help="Project name for the tarball prefix",
    )
    args = parser.parse_args()
    if not args.project_name:
        args.project_name = github.repository_name()
    return Config(**vars(args))


def create_tarballs(project_name: str, tag: str, tmpdir: str) -> None:
    """Create source tarballs with both .gz and .xz for the given tag."""
    for prog in ("gzip", "xz"):
        tarname = f"{os.path.join(tmpdir, tag)}.tar"
        print(f"Creating {prog} tarball for {tag}")
        subprocess.run(  # nosec
            [
                "git",
                "archive",
                "--format=tar",
                f"--prefix={project_name}-{tag}/",
                tag,
                f"--output={tarname}",
            ],
            check=True,
        )
        subprocess.run([prog, "-f", tarname], check=True)  # nosec


def upload_tarballs(tag: str, tmpdir: str) -> None:
    """Upload the tarballs to GitHub."""
    content_type = {
        "gz": "application/gzip",
        "xz": "application/x-xz",
    }
    for ext in ("gz", "xz"):
        filename = f"{tag}.tar.{ext}"
        print(f"Uploading {filename} to GitHub release {tag}")
        with open(os.path.join(tmpdir, filename), "rb") as f:
            github.upload_asset(tag, filename, content_type[ext], f)


def main(config: Config) -> None:
    if config.upload:
        with tempfile.TemporaryDirectory() as tmpdir:
            create_tarballs(config.project_name, config.tag, tmpdir)
            upload_tarballs(config.tag, tmpdir)
    else:
        create_tarballs(config.project_name, config.tag, ".")


if __name__ == "__main__":
    main(parse_args())
