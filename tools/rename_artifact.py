#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025 The TokTok team
import os
import re
import sys


def _has_glob(s: str) -> bool:
    return any(c in r"*{}" for c in s)


def _glob_to_regex(original: str, renamed: str) -> tuple[str, str]:
    i = 1
    while _has_glob(original) and _has_glob(renamed):
        if "*" in renamed:
            if "*" not in original:
                print(f"Error: * not in {original}")
                sys.exit(1)
            original = original.replace("*", "(.+)", 1)
            renamed = renamed.replace("*", f"\\{i}", 1)
            i += 1
        if "{" in renamed and "}" in renamed:
            choice = renamed[renamed.index("{"):renamed.index("}") + 1]
            if choice not in original:
                print(f"Error: {choice} not in {original}")
                sys.exit(1)
            matcher = choice[1:-1].replace(",", "|")
            original = original.replace(choice, f"({matcher})", 1)
            renamed = renamed.replace(choice, f"\\{i}", 1)
            i += 1
    return original, renamed


def _write_github_outputs(outputs: list[str]):
    if "GITHUB_ACTIONS" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("artifacts<<EOF\n")
            for output in outputs:
                f.write(f"{output}\n")
            f.write("EOF\n")


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <original> <renamed> [files...]")
        sys.exit(1)

    original = sys.argv[1]
    renamed = sys.argv[2]
    files = sys.argv[3:]

    print(f"Copying {original} to {renamed}")

    original_re, renamed_re = _glob_to_regex(original, renamed)

    print(f"Copying {original_re} to {renamed_re}")
    print(f"Found {len(files)} files: {files}")
    outputs: list[str] = []
    for f in files:
        new_name = re.sub(original_re, renamed_re, f)
        print(f"Copying {f} to {new_name}")
        try:
            with open(f, "rb") as src, open(new_name, "wb") as dst:
                dst.write(src.read())
            outputs.append(new_name)
        except Exception as e:
            print(f"Error Copying {f} to {new_name}: {e}")

    print(f"Renamed {len(outputs)} files: {outputs}")
    _write_github_outputs(outputs)
    print("Done")


if __name__ == "__main__":
    main()
