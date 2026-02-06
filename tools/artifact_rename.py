#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2025-2026 The TokTok team
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
            choice = renamed[renamed.index("{") : renamed.index("}") + 1]
            if choice not in original:
                print(f"Error: {choice} not in {original}")
                sys.exit(1)
            matcher = choice[1:-1].replace(",", "|")
            original = original.replace(choice, f"({matcher})", 1)
            renamed = renamed.replace(choice, f"\\{i}", 1)
            i += 1
    # The remaining globs are in the original only and are turned into
    # non-capturing groups so file name regexp matching works.
    while _has_glob(original):
        if "*" in original:
            original = original.replace("*", ".+", 1)
        if "{" in original and "}" in original:
            choice = original[original.index("{") : original.index("}") + 1]
            matcher = choice[1:-1].replace(",", "|")
            original = original.replace(choice, f"(?:{matcher})", 1)
    return original, renamed


def _write_github_outputs(outputs: list[str]) -> None:
    if "GITHUB_ACTIONS" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("artifacts<<EOF\n")
            for output in outputs:
                f.write(f"{output}\n")
            f.write("EOF\n")


def main() -> None:
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <original> <renamed> [files...]")
        sys.exit(1)

    original = sys.argv[1].split(" ")
    renamed = sys.argv[2].split(" ")
    files = sys.argv[3:]

    if len(original) != len(renamed):
        print(f"Error: {len(original)} original and {len(renamed)} renamed")
        sys.exit(1)

    print(f"Found {len(files)} files: {files}")

    outputs: list[str] = []
    for o, r in zip(original, renamed):
        print(f"Copying glob {o} to {r}")

        o_re, r_re = _glob_to_regex(o, r)

        print(f"Copying regex {o_re} to {r_re}")
        o_files = [f for f in files if re.match(o_re, f)]
        if not o_files:
            print(f"Error: no files match {o_re}")
            sys.exit(1)
        for f in o_files:
            if not re.match(o_re, f):
                continue
            new_name = re.sub(o_re, r_re, f)
            print(f"Copying file {f} to {new_name}")
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
