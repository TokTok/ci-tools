#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import argparse
import sys
from dataclasses import dataclass

import verify_appimage
import verify_common
from lib import git


@dataclass
class Config:
    tag: str
    repo: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="Run all reproducibility verifications."
    )
    parser.add_argument("--tag", help="Tag to verify", default=git.current_tag())
    parser.add_argument(
        "--repo", help="Repository name", default=verify_common.get_default_repo()
    )
    return Config(**vars(parser.parse_args()))


def main(config: Config) -> int:
    tag = config.tag
    repo = config.repo

    failed = []

    print(f"--- Running verify_appimage for {repo} {tag} ---", file=sys.stderr)
    appimage_config = verify_appimage.Config(tag=tag, repo=repo)
    if verify_appimage.main(appimage_config) != 0:
        failed.append("verify_appimage.py")

    if failed:
        print(f"Verifications failed: {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"All verifications passed for {repo} {tag}!", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(parse_args()))
