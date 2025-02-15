#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025 The TokTok team
import os
import subprocess  # nosec
import sys


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project-name> <files...>")
        sys.exit(1)

    project_name = sys.argv[1]
    files = sys.argv[2:]

    outputs: list[str] = []
    for file in files:
        sha256 = subprocess.check_output(["sha256sum", file])  # nosec
        with open(f"{file}.sha256", "wb") as f:
            f.write(sha256)
        outputs.append(file)
        outputs.append(f"{file}.sha256")

    if "GITHUB_ACTIONS" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("artifacts<<EOF\n")
            for output in outputs:
                f.write(f"{output}\n")
            f.write("EOF\n")

            if not project_name:
                project_name = (
                    subprocess.check_output(  # nosec
                        [
                            "pcregrep",
                            "-M",
                            "-o1",
                            r"project\(\s*(\S+)",
                            "CMakeLists.txt",
                        ]).decode().strip())
            f.write(f"project-name={project_name}\n")


if __name__ == "__main__":
    main()
