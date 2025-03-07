#!/usr/bin/env python3
import argparse
import io
import os
import zipfile
from dataclasses import dataclass

from lib import git
from lib import github


@dataclass
class Config:
    branch: str
    force: bool


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Update test goldens from the latest failed GitHub check.
    """)
    parser.add_argument(
        "--branch",
        help="Git branch to use for the golden update.",
        required=False,
        default=git.current_branch(),
    )
    parser.add_argument(
        "--force",
        help="Force the update even if the latest check did not (yet) fail.",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    return Config(**vars(parser.parse_args()))


def _discover_goldens() -> dict[str, str]:
    """Find all the .png files in test/**/*."""
    goldens: dict[str, str] = {}
    for root, _, files in os.walk("test"):
        for file in files:
            if file.endswith(".png"):
                base = file.removesuffix(".png")
                if base in goldens:
                    raise ValueError(f"Duplicate golden image: {base}")
                goldens[base] = os.path.join(root, file)
    return goldens


def main(config: Config) -> None:
    os.chdir(git.root_dir())
    goldens = _discover_goldens()

    sha = git.branch_sha(config.branch)
    checks = github.action_runs(config.branch, sha)
    for check in checks:
        if check.path == ".github/workflows/ci.yml":
            if not config.force and check.conclusion != "failure":
                print(f"Check for {config.branch}@{sha} did not fail; "
                      "no golden images to update.")
                return
            content = github.download_artifact("failed-test-goldens", check.id)
            zip_buffer = io.BytesIO(content)
            with zipfile.ZipFile(zip_buffer) as z:
                for file in z.filelist:
                    print(f"Checking {file.filename}")
                    if file.filename.endswith("_testImage.png"):
                        base = os.path.basename(
                            file.filename.removesuffix("_testImage.png"))
                        if base in goldens:
                            print(f"Updating {base}.png")
                            with z.open(file) as f:
                                with open(goldens[base], "wb") as out:
                                    out.write(f.read())
                        else:
                            print(f"Unknown golden image: {base}")


if __name__ == "__main__":
    main(parse_args())
