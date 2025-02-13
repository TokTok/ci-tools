#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import argparse
import multiprocessing
import os
import subprocess  # nosec
import sys
import tempfile
from dataclasses import dataclass

from lib import git
from lib import github

NEEDS_SIGNATURE = (".AppImage", ".apk", ".dmg", ".exe", ".flatpak", ".gz",
                   ".xz")


@dataclass
class Config:
    tag: str


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Download binaries and signatures from the GitHub release and verify the
    signatures.
    """)
    parser.add_argument(
        "--tag",
        help="Tag to create signatures for",
        default=git.current_tag(),
    )
    return Config(**vars(parser.parse_args()))


def verify_signature(tmpdir: str, binary: str) -> None:
    subprocess.run(  # nosec
        [
            "gpg",
            "--verify",
            os.path.join(tmpdir, f"{binary}.asc"),
            os.path.join(tmpdir, binary),
        ],
        check=True,
    )


def download_and_verify(
    args: tuple[str, github.ReleaseAsset, dict[str,
                                               github.ReleaseAsset]]) -> None:
    tmpdir, asset, by_name = args
    print(f"Downloading {asset.name} and {asset.name}.asc", file=sys.stderr)
    with open(os.path.join(tmpdir, asset.name), "wb") as f:
        f.write(github.download_asset(asset.id))
    with open(os.path.join(tmpdir, f"{asset.name}.asc"), "wb") as f:
        f.write(github.download_asset(by_name[asset.name + ".asc"].id))
    verify_signature(tmpdir, asset.name)


def download_and_verify_binaries(config: Config, tmpdir: str) -> None:
    assets = github.release_assets(config.tag)
    by_name = {asset.name: asset for asset in assets}
    todo = [asset for asset in assets if asset.name.endswith(NEEDS_SIGNATURE)]
    with multiprocessing.Pool() as pool:
        pool.map(download_and_verify,
                 [(tmpdir, asset, by_name) for asset in todo])


def main(config: Config) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        download_and_verify_binaries(config, tmpdir)


if __name__ == "__main__":
    main(parse_args())
