#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2021 by The qTox Project Contributors
# Copyright © 2024-2026 The TokTok team
import argparse
import json
import pathlib
import re
import subprocess  # nosec
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any

from lib import git


def toktok_root() -> pathlib.Path:
    return git.root_dir().parent


def download_file_paths() -> pathlib.Path:
    return toktok_root() / "dockerfiles" / "qtox" / "download"


@dataclass
class Config:
    flathub_manifest_path: str
    output_manifest_path: str
    download_files_path: str
    git_tag: str | None
    quiet: bool


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Update dependencies of a flathub manifest to match the versions used by
    qTox. This script will iterate over all known dependencies in the manifest
    and replace their tags with the ones specified by our download_xxx.sh
    scripts.
    """)
    parser.add_argument(
        "--flathub-manifest",
        help="Path to flathub manifest",
        required=False,
        dest="flathub_manifest_path",
    )
    parser.add_argument(
        "--output",
        help="Output manifest path (defaults to --flathub-manifest path)",
        required=False,
        dest="output_manifest_path",
    )
    parser.add_argument(
        "--download-files-path",
        help="Path to the dockerfiles/qtox/download directory",
        required=False,
        default=download_file_paths(),
    )
    parser.add_argument(
        "--git-tag",
        help="Git tag to use for the qTox version",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--quiet",
        help="Suppress output",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return Config(**vars(parser.parse_args()))


PRINT_VERSION_SCRIPT = """
download_verify_extract_tarball() {
    echo "URL: $1"
    echo "HASH: $2"
}
"""


def extract_version_and_hash(output: str) -> tuple[str, str]:
    """Extract the version and hash from the bash script output."""
    matches = re.match(r"URL: (.*)\nHASH: (.*)", output, re.MULTILINE)
    if matches is None:
        raise ValueError("Failed to extract version and hash from download script")
    return matches.group(1), matches.group(2)


def find_version(download_script_path: pathlib.Path) -> tuple[str, str]:
    """
    Find the version and hash specified for a given dependency by parsing its
    download script.

    Returns a tuple of (version, hash).
    """
    with open(download_script_path) as f:
        script_content = "".join(
            re.sub(r"^source.*", PRINT_VERSION_SCRIPT, line) for line in f.readlines()
        )

    # Run bash script in a sub-shell to extract the version
    version_output = subprocess.check_output(  # nosec
        ["bash", "-c", script_content],
    ).decode()

    return extract_version_and_hash(version_output)


def load_flathub_manifest(flathub_manifest_path: str) -> Any:
    with open(flathub_manifest_path) as f:
        return json.load(f)


def commit_from_tag(url: str, tag: str) -> str:
    if tag.startswith("release/"):
        output = subprocess.check_output(["git", "rev-parse", tag])  # nosec
        return output.decode().strip()

    return (
        subprocess.check_output(  # nosec
            ["git", "ls-remote", url, f"{tag}^{{}}"],
        )
        .split(b"\t")[0]
        .decode()
    )


def update_archive_source(
    module: dict[str, Any],
    source: tuple[str, str],
) -> None:
    url, sha256 = source
    module_source = module["sources"][0]
    module_source["url"] = url
    module_source["sha256"] = sha256


def update_git_source(module: dict[str, Any], tag: str) -> None:
    module_source = module["sources"][0]
    if module_source["type"] == "git":
        module_source["tag"] = tag
        module_source["commit"] = commit_from_tag(
            module_source["url"],
            tag,
        )


def find_manifest() -> pathlib.Path | None:
    for path in (git.root_dir() / "platform" / "flatpak").rglob("*.json"):
        return path
    return None


def _normalize(name: str) -> str:
    return name.lower().replace("-", "").replace("_", "")


def map_module_name(module_name: str) -> str:
    """Map a Flathub module name to our internal download script filename."""
    download_file_map = {
        "libsodium": "sodium",
        "c-toxcore": "toxcore",
    }
    return download_file_map.get(module_name, module_name)


def main(config: Config) -> None:
    if not config.flathub_manifest_path:
        # Try to detect where the manifest is. See if there's a single
        # platform/flatpak/*.json file. If yes, use that.
        manifest_path = find_manifest()
        if not manifest_path:
            raise ValueError(
                "No manifest path provided and couldn't detect one automatically"
            )
        config.flathub_manifest_path = str(manifest_path)
        print("Detected manifest path:", config.flathub_manifest_path)

    if not config.output_manifest_path:
        config.output_manifest_path = config.flathub_manifest_path

    flathub_manifest = load_flathub_manifest(config.flathub_manifest_path)

    self_version = config.git_tag or git.current_tag()
    self_name = _normalize(git.root_dir().name)
    print("Using version", self_version, "for", self_name)

    download_files_dir = pathlib.Path(config.download_files_path)

    for module in flathub_manifest["modules"]:
        module_name = str(module["name"])
        if _normalize(module_name) == self_name:
            update_git_source(module, self_version)
        else:
            filename = map_module_name(module_name)
            update_archive_source(
                module, find_version(download_files_dir / f"download_{filename}.sh")
            )

    orig = load_flathub_manifest(config.output_manifest_path)
    if json.dumps(flathub_manifest) != json.dumps(orig):
        print("Changes detected, writing to", config.output_manifest_path)
        with open(config.output_manifest_path, "w") as f:
            json.dump(flathub_manifest, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main(parse_args())
