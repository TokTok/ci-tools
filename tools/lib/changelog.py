# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import re
from dataclasses import dataclass

DEFAULT_LOGFILE = "CHANGELOG.md"


@dataclass
class ReleaseNotes:
    version: str
    date: str
    header: str
    notes: str
    changelog: str

    def formatted(self) -> str:
        text = f"{self.header}\n"
        if self.notes:
            text += f"\n{self.notes}\n"
        if self.changelog:
            text += f"\n{self.changelog}\n"
        return text


def parse(logfile: str = DEFAULT_LOGFILE) -> dict[str, ReleaseNotes]:
    """Parse the changelog file and return a dictionary of release notes.

    - "v0.1.3-rc.1" is the version.
    - "2025-02-14" is the date.
    - "#### Release notes" is the header.
    - "Some release notes here." is the notes.
    - "#### Features" and the text until the next version is the changelog.
    """
    messages: dict[str, ReleaseNotes] = {}

    with open(logfile, "r") as f:
        lines = f.read().splitlines()

    version = date = header = notes = changelog = ""
    in_release_notes = in_changelog = False

    for line in lines:
        if in_release_notes:
            if line.startswith("####"):
                in_release_notes = False
                in_changelog = True
            elif line.startswith("<a name="):
                in_release_notes = False
                messages[version] = ReleaseNotes(version, date, header,
                                                 notes.strip(),
                                                 changelog.strip())
            else:
                notes += line + "\n"
                continue
        if in_changelog:
            if line.startswith("<a name="):
                in_changelog = False
                messages[version] = ReleaseNotes(version, date, header,
                                                 notes.strip(),
                                                 changelog.strip())
            else:
                changelog += line + "\n"
                continue
        if line.startswith("## "):
            if version:
                messages[version] = ReleaseNotes(version, date, header,
                                                 notes.strip(),
                                                 changelog.strip())
            version = line.split(" ")[1]
            date = line.split("(")[1].split(")")[0]
            header = ""
            notes = ""
            changelog = ""
        if line.startswith("### "):
            header = line
            notes = ""
            in_release_notes = True

    if version:
        messages[version] = ReleaseNotes(version, date, header, notes.strip(),
                                         changelog.strip())

    return messages


def get_release_notes(version: str,
                      logfile: str = DEFAULT_LOGFILE) -> ReleaseNotes:
    return parse(logfile)[version]


def has_release_notes(version: str, logfile: str = DEFAULT_LOGFILE) -> bool:
    return parse(logfile).get(version) is not None


def set_release_notes(version: str,
                      notes: str,
                      logfile: str = DEFAULT_LOGFILE) -> None:
    """Set the release notes for a given version in the changelog file.

    Release notes are inserted between version header "## <version>" and the
    next version header "<a name=...>" or the actual changelog "#### Features".
    """
    with open(logfile, "r") as f:
        lines = f.read().splitlines()

    updated = []
    in_release_notes = False
    wrote_notes = False
    for line in lines:
        if in_release_notes:
            if not wrote_notes:
                updated.append(f"\n{notes.strip()}\n")
                wrote_notes = True
            if line.startswith("<a name=") or line.startswith("####"):
                in_release_notes = False
            else:
                continue
        updated.append(line)
        if line.startswith("## " + version):
            in_release_notes = True

    with open(logfile, "w") as f:
        f.write("\n".join(updated) + "\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: changelog.py <logfile> <version> [<notes>]")
        sys.exit(1)

    logfile = sys.argv[1]
    version = sys.argv[2]
    notes = sys.argv[3] if len(sys.argv) > 3 else None

    if notes is None:
        print(get_release_notes(version, logfile).formatted())
    else:
        set_release_notes(version, notes, logfile)
