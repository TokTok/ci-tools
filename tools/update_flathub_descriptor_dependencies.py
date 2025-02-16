#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2021 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team
import argparse
import json
import pathlib
import re
import subprocess  # nosec
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any
from typing import Optional

from lib import git

GIT_ROOT = git.root_dir()
TOKTOK_ROOT = GIT_ROOT.parent
DOWNLOAD_FILE_PATHS = TOKTOK_ROOT / "dockerfiles" / "qtox" / "download"


@dataclass
class Config:
    flathub_manifest_path: str
    output_manifest_path: str
    download_files_path: str
    git_tag: Optional[str]
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
        default=DOWNLOAD_FILE_PATHS,
        dest="download_files_path",
    )
    parser.add_argument(
        "--git-tag",
        help="Git tag to use for the qTox version",
        required=False,
        default=None,
        dest="git_tag",
    )
    parser.add_argument(
        "--quiet",
        help="Suppress output",
        action=argparse.BooleanOptionalAction,
        default=False,
        dest="quiet",
    )
    return Config(**vars(parser.parse_args()))


PRINT_VERSION_SCRIPT = """
download_verify_extract_tarball() {
    echo "URL: $1"
    echo "HASH: $2"
}
"""


def find_version(download_script_path: pathlib.Path) -> tuple[str, str]:
    """
    Find the version and hash specified for a given dependency by parsing its
    download script.

    Returns a tuple of (version, hash).
    """
    with open(download_script_path) as f:
        script_content = "".join(
            re.sub(r"^source.*", PRINT_VERSION_SCRIPT, line)
            for line in f.readlines())

    # Run bash script in a sub-shell to extract the version
    version_output = subprocess.check_output(  # nosec
        ["bash", "-c", script_content], ).decode()

    # Extract the version and hash from the output
    matches = re.match(r"URL: (.*)\nHASH: (.*)", version_output, re.MULTILINE)
    if matches is None:
        raise ValueError(
            "Failed to extract version and hash from download script")

    return matches.group(1), matches.group(2)


class FindVersionTest(unittest.TestCase):

    def test_version_parsing(self) -> None:
        # Create a dummy download script and check that we can extract the version from it
        with tempfile.TemporaryDirectory() as d:
            sample_download_script = """
            #!/bin/bash

            source "$(dirname "$0")"/common.sh

            TEST_VERSION=1.2.3
            TEST_HASH=:)

            download_verify_extract_tarball \
                "https://test_site.com/$TEST_VERSION" \
                "$TEST_HASH"
            """

            sample_download_script_path = pathlib.Path(d) / "/test_script.sh"
            with open(sample_download_script_path, "w") as f:
                f.write(sample_download_script)

            self.assertEqual(find_version(sample_download_script_path),
                             ("1.2.3", ":)"))


def load_flathub_manifest(flathub_manifest_path: str) -> Any:
    with open(flathub_manifest_path) as f:
        return json.load(f)


def commit_from_tag(url: str, tag: str) -> str:
    if tag.startswith("release/"):
        output = subprocess.check_output(["git", "rev-parse", tag])  # nosec
        return output.decode().strip()

    return (subprocess.check_output(  # nosec
        ["git", "ls-remote", url, f"{tag}^{{}}"], ).split(b"\t")[0].decode())


class CommitFromTagTest(unittest.TestCase):

    def test_commit_from_tag(self) -> None:
        # Must be run in the qTox repository.
        self.assertEqual(
            commit_from_tag(str(GIT_ROOT), "v1.17.3"),
            "c0e9a3b79609681e5b9f6bbf8f9a36cb1993dc5f",
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


def find_manifest() -> Optional[pathlib.Path]:
    for path in (GIT_ROOT / "platform" / "flatpak").rglob("*.json"):
        return path
    return None


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
    self_name = GIT_ROOT.name.lower()

    download_files_dir = pathlib.Path(config.download_files_path)
    download_file_map = {
        "libsodium": "sodium",
        "c-toxcore": "toxcore",
    }

    for module in flathub_manifest["modules"]:
        module_name = str(module["name"])
        if module_name.lower().replace("-", "") == self_name:
            update_git_source(module, self_version)
        else:
            filename = download_file_map.get(module_name, module_name)
            update_archive_source(
                module,
                find_version(download_files_dir / f"download_{filename}.sh"))

    orig = load_flathub_manifest(config.output_manifest_path)
    if json.dumps(flathub_manifest) != json.dumps(orig):
        print("Changes detected, writing to", config.output_manifest_path)
        with open(config.output_manifest_path, "w") as f:
            json.dump(flathub_manifest, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main(parse_args())
