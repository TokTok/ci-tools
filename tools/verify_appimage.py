#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2026 The TokTok team
import argparse
import os
import shutil
import subprocess  # nosec
import sys
from dataclasses import dataclass

import verify_common
from lib import git, github


@dataclass
class Config:
    tag: str
    repo: str
    project_name: str | None = None


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Verify AppImage reproducibility.")
    parser.add_argument("--tag", help="Tag to verify", default=git.current_tag())
    parser.add_argument(
        "--repo", help="Repository name", default=verify_common.get_default_repo()
    )
    parser.add_argument(
        "--project-name", help="Project name (defaults to repo name)", default=None
    )
    return Config(**vars(parser.parse_args()))


def get_sha256(path: str) -> str:
    sha = subprocess.check_output(["sha256sum", path], text=True)  # nosec
    return sha.split()[0]


def main(config: Config) -> int:
    repo_name = config.repo
    tag = config.tag

    gh = github.GitHub()

    with verify_common.Workspace(repo_name, tag) as workspace:
        # Detect project name from the workspace (the cloned repo)
        project_name = config.project_name or verify_common.detect_project_name(
            workspace.root
        )

        if not project_name:
            print(
                f"Error: Could not detect project name from {workspace.root}/CMakeLists.txt",
                file=sys.stderr,
            )
            print("Please provide it manually using --project-name", file=sys.stderr)
            return 1

        print(f"Detected project name: {project_name}", file=sys.stderr)

        assets = gh.release_assets(tag)
        # Search for AppImage assets matching the detected project name.
        appimage_asset = next(
            (
                a
                for a in assets
                if a.name.lower().startswith(project_name.lower())
                and a.name.lower().endswith(".appimage")
                and "x86_64" in a.name.lower()
            ),
            None,
        )

        if not appimage_asset:
            print(
                f"No x86_64 AppImage found for tag {tag} matching {project_name}",
                file=sys.stderr,
            )
            return 1

        released_path = os.path.join(workspace.root, "released.AppImage")
        print(f"Downloading {appimage_asset.name}...", file=sys.stderr)
        with open(released_path, "wb") as f:
            f.write(gh.download_asset(appimage_asset.id))

        # 2. Build local
        print("Building local AppImage via Docker...", file=sys.stderr)
        workspace.run_docker(
            "alpine-appimage",
            [
                "third_party/ci-tools/platform/appimage/build.sh",
                "--arch",
                "x86_64",
                "--src-dir",
                "/qtox",
                "--project-name",
                project_name,
                "--",
            ],
            env={
                "GITHUB_REPOSITORY": f"TokTok/{repo_name}",
                "GITHUB_REF": f"refs/tags/{tag}",
            },
        )
        print("Build completed successfully.", file=sys.stderr)

        # Find the produced AppImage in the workspace root
        # Filename format: $PROJECT_NAME-$(git rev-parse --short HEAD | head -c7)-$ARCH.AppImage
        sha = subprocess.check_output(  # nosec
            ["git", "-C", workspace.root, "rev-parse", "--short", "HEAD"], text=True
        ).strip()[:7]
        local_name = f"{project_name}-{sha}-x86_64.AppImage"
        local_path = os.path.join(workspace.root, local_name)

        if not os.path.exists(local_path):
            print(f"Local build failed to produce {local_path}", file=sys.stderr)
            return 1

        # 3. Compare
        print("Comparing released and local AppImages...", file=sys.stderr)

        released_sha = get_sha256(released_path)
        local_sha = get_sha256(local_path)

        print(f"Released SHA256: {released_sha}")
        print(f"Local SHA256:    {local_sha}")

        if released_sha != local_sha:
            print("AppImages differ!", file=sys.stderr)

            # Deep investigation
            print("\n--- Deep Investigation ---", file=sys.stderr)
            released_dir = os.path.join(workspace.root, "released_ext")
            local_dir = os.path.join(workspace.root, "local_ext")

            def extract_appimage(path: str, out: str) -> None:
                """Extract SquashFS content from AppImage."""
                # AppImages extract themselves when called with --appimage-extract
                # We make sure it's executable first.
                os.chmod(path, 0o755)  # nosec
                try:
                    # In some environments (like Docker/restricted shells),
                    # we might need --appimage-extract-and-run or specific env vars.
                    # But usually this is the most direct way.
                    subprocess.run(  # nosec
                        [path, "--appimage-extract"],
                        cwd=workspace.root,
                        check=True,
                        capture_output=True,
                    )
                    target_squash = os.path.join(workspace.root, "squashfs-root")
                    if os.path.exists(target_squash):
                        shutil.move(target_squash, out)
                    else:
                        print(
                            f"Extraction of {path} failed to produce squashfs-root",
                            file=sys.stderr,
                        )
                except Exception as e:
                    print(f"Extraction of {path} failed: {e}", file=sys.stderr)
                    # Fallback to unsquashfs if the binary can't run
                    subprocess.run(  # nosec
                        ["unsquashfs", "-d", out, "-f", path],
                        check=True,
                        capture_output=True,
                    )

            try:
                print("Extracting released AppImage...", file=sys.stderr)
                extract_appimage(released_path, released_dir)
                print("Extracting local AppImage...", file=sys.stderr)
                extract_appimage(local_path, local_dir)

                print("Comparing extracted filesystem contents...", file=sys.stderr)
                # Compare file structures and content hashes
                diff_proc = subprocess.run(  # nosec
                    ["diff", "-rq", released_dir, local_dir],
                    capture_output=True,
                    text=True,
                )

                if diff_proc.returncode == 0:
                    print(
                        "SUCCESS: Filesystem contents are bit-for-bit identical!",
                        file=sys.stderr,
                    )
                    print(
                        "The difference lies solely in the AppImage packaging (SquashFS metadata or Runtime).",
                        file=sys.stderr,
                    )
                else:
                    print("DIFFERENCES FOUND in filesystem contents:", file=sys.stderr)
                    print(diff_proc.stdout)

                    # Run diffoscope on the directories for a detailed breakdown
                    if shutil.which("diffoscope"):
                        print(
                            "\nRunning diffoscope on extracted directories...",
                            file=sys.stderr,
                        )
                        # Limit output to avoid huge logs
                        subprocess.run(  # nosec
                            ["diffoscope", "--text", "-", released_dir, local_dir]
                        )
            except Exception as e:
                print(f"Deep investigation failed: {e}", file=sys.stderr)

            # Always run diffoscope on the full AppImage as a final reference
            if shutil.which("diffoscope"):
                print("\n--- Full AppImage Diff (Reference) ---", file=sys.stderr)
                subprocess.run(["diffoscope", released_path, local_path])  # nosec

            return 1
        else:
            print("AppImages are identical!", file=sys.stderr)
            return 0


if __name__ == "__main__":
    sys.exit(main(parse_args()))
