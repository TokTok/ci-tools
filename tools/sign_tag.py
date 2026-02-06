#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025-2026 The TokTok team
import argparse
import sys
from dataclasses import dataclass

from lib import git


@dataclass
class Config:
    tag: str
    upstream: str
    verify_only: bool
    local_only: bool


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Force-sign and force-push the latest tag. If the tag is already signed,
    this tool does nothing.
    """)
    parser.add_argument(
        "--tag",
        help="Tag to create signatures for",
        default="",
    )
    parser.add_argument(
        "--upstream",
        help="Upstream remote to push to",
        default="upstream",
    )
    parser.add_argument(
        "--verify-only",
        help="Verify the tag signature",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    parser.add_argument(
        "--local-only",
        help="Create, but do not push the signed tag",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return Config(**vars(parser.parse_args()))


def main(config: Config) -> None:
    git.fetch(config.upstream)
    if not config.tag:
        config.tag = git.current_tag()
    if git.tag_has_signature(config.tag):
        print(f"Tag {config.tag} already signed")
        if config.verify_only:
            if not git.verify_tag(config.tag):
                print(f"Tag {config.tag} signature cannot be verified")
                sys.exit(1)
        return
    if config.verify_only:
        print(f"Tag {config.tag} is not signed")
        sys.exit(1)
    print(f"Signing tag {config.tag}")
    git.sign_tag(config.tag)
    if not config.local_only:
        git.push_tag(config.tag, config.upstream)


if __name__ == "__main__":
    main(parse_args())
