# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import re

DEFAULT_LOGFILE = "CHANGELOG.md"


def _insert(messages: dict[str, str], version: str,
            message: list[str]) -> None:
    while message and not message[-1].strip():
        message.pop()
    while message and not message[0].strip():
        message.pop(0)
    messages[version] = "\n".join(message)


def parse(logfile: str = DEFAULT_LOGFILE) -> dict[str, str]:
    messages: dict[str, str] = {}

    with open(logfile, "r") as f:
        version = None
        message: list[str] = []
        for line in f.read().splitlines():
            version_found = re.search(r"^##\s*(v[^ ]+)", line)
            if version_found:
                version = version_found.group(1)
                continue
            if version:
                if line.startswith("####") or line.startswith("<a name="):
                    _insert(messages, version, message)
                    version = None
                    message = []
                else:
                    message.append(line)
        if version:
            _insert(messages, version, message)

    return messages


def get_release_notes(version: str, logfile: str = DEFAULT_LOGFILE) -> str:
    return parse(logfile)[version]


def has_release_notes(version: str, logfile: str = DEFAULT_LOGFILE) -> bool:
    return parse(logfile).get(version) is not None
