#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
import argparse
import os
import pathlib
import re
import subprocess  # nosec
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from lib import changelog, git

# b2215454e chore(windows): update copyright year
# d44fc4dfe chore: Add script for syncing CHANGELOG.md to git tags.
COMMIT_REGEX = re.compile(
    r"(?P<category>(?:chore|fix|feat|perf|docs|refactor|revert|test|style)):?(?:\((?P<module>[^)]+)\))?:\s*(?P<message>.+)"
)

# 977b7fc9a02b2b44164ffb77ab35f4cdfae90542
# Author: sudden6 <sudden6@gmx.at>
# Date:   Sat Jun 23 15:18:12 2018 +0200
#
#     fix(settings): automatically disable UDP when a proxy is set
#
#     fixes: #5174
LOG_REGEX = re.compile(
    r"^(?P<sha>[0-9a-f]+)(?:\nMerge:(?: [0-9a-f]+)+)?(?:\nAuthor: (?P<author>.+))?(?:\nDate:   (?P<date>.+))?\n\n(?P<message>(?:.|\n)+)",
    re.MULTILINE,
)

CATEGORIES = ["feat", "fix", "perf"]


def category_name(category: str) -> str:
    return {
        "feat": "Features",
        "fix": "Bug Fixes",
        "perf": "Performance",
        "docs": "Documentation",
        "style": "Styles",
        "refactor": "Code Refactoring",
        "test": "Tests",
        "chore": "Chores",
        "revert": "Reverts",
        "misc": "Miscellaneous",
    }[category]


@dataclass
class LogEntry:
    repository: str
    sha: str
    author: str
    date: str
    category: str
    module: Optional[str]
    message: str
    closes: tuple[str, ...]


@dataclass
class ForkInfo:
    repository: str
    since: str


@dataclass
class Config:
    changelog: str
    production: bool
    repository: str
    forked_from: list[ForkInfo]
    ignore_before: Optional[str]


def read_clog_toml() -> dict[str, Any]:
    toml = pathlib.Path(git.root_dir()) / ".clog.toml"
    if not toml.is_file():
        return {}
    with open(toml, "rb") as f:
        return tomllib.load(f)


def parse_fork_config(data: list[dict[str, Any]]) -> list[ForkInfo]:
    return [ForkInfo(repository=d["repository"], since=d["since"]) for d in data]


def parse_config(data: dict[str, Any]) -> Config:
    return Config(
        changelog=data.get("clog", {})["changelog"],
        production=data.get("clog", {}).get("production", False),
        repository=data.get("clog", {}).get("repository", "http://localhost/"),
        forked_from=parse_fork_config(data.get("clog", {}).get("forked-from", {})),
        ignore_before=data.get("clog", {}).get("ignore-before", None),
    )


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="""
    Update the CHANGELOG.md file with the commits between the current tag and
    the previous tag. Rebuilds the entire CHANGELOG.md file using all tags.

    Somewhat compatible with clog-cli.
    """)
    clog_config = parse_config(read_clog_toml())
    parser.add_argument(
        "--changelog",
        help="Path to the CHANGELOG.md file",
        default=clog_config.changelog,
    )
    parser.add_argument(
        "--production",
        action=argparse.BooleanOptionalAction,
        help="Production mode: ignore release candidates",
        default=clog_config.production,
    )
    parser.add_argument(
        "--repository",
        help="URL to the repository",
        default=clog_config.repository,
    )
    parser.add_argument(
        "--forked-from",
        help="Forked from repository",
        action="append",
        default=clog_config.forked_from,
    )
    parser.add_argument(
        "--ignore-before",
        help="Ignore everything before and including this tag",
        default=clog_config.ignore_before,
    )
    return Config(**vars(parser.parse_args()))


def git_log(prev_tag: str, cur_tag: str) -> list[str]:
    log = subprocess.check_output(
        [  # nosec
            "git",
            "log",
            f"{prev_tag}..{cur_tag}",
        ]
    )
    return log.decode("utf-8").removeprefix("commit ").split("\ncommit ")


def git_tag_date(tag: str) -> str:
    tag_sha = (
        subprocess.check_output(  # nosec
            [
                "git",
                "rev-parse",
                tag,
            ]
        )
        .decode("utf-8")
        .strip()
    )
    tag_data = subprocess.check_output(  # nosec
        [
            "git",
            "cat-file",
            "-p",
            tag_sha,
        ]
    ).decode("utf-8")
    date_match = re.search(r"^Original tagger: .+ (\d{10})", tag_data, re.MULTILINE)
    if not date_match:
        date_match = re.search(r"^tagger .+ (\d{10})", tag_data, re.MULTILINE)
    if not date_match:
        date_match = re.search(r"^committer .+ (\d{10})", tag_data, re.MULTILINE)
    if not date_match:
        raise Exception(f"Date not found for tag {tag}")

    return datetime.fromtimestamp(int(date_match.group(1))).strftime("%Y-%m-%d")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def unindent(text: str) -> str:
    lines = text.split("\n")
    indent = len(lines[0]) - len(lines[0].lstrip())
    return "\n".join(line[indent:].rstrip() for line in lines)


def parse_closes(message: str) -> list[str]:
    return [
        fix
        for fixes in re.findall(
            r"(?:closes|fix|fixe[ds]|resolve[ds]):?\s+((?:#\d+(?:,\s*)?)+)",
            message,
            re.IGNORECASE,
        )
        for fix in re.findall(r"#(\d+)", fixes)
    ]


def next_repo(repo: str, forks: list[ForkInfo], sha: str) -> str:
    for fork in forks:
        if sha.startswith(fork.since):
            return fork.repository
    return repo


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class LogParser:

    def __init__(self, config: Config) -> None:
        self.config = config
        self.repository = config.repository

    def parse_log(self, log: list[str]) -> list[LogEntry]:
        """
        a83ef30476012d3840582ddea64cf180285beb4f
        Author: Anthony Bilinski <me@abilinski.com>
        Date:   Sat Mar 5 04:20:45 2022 -0800

            chore(release): Add changelog
        """
        entries = []
        for entry in log:
            matches = re.match(LOG_REGEX, entry)
            if not matches:
                raise Exception(f"Failed to parse log entry: {entry}")
            sha = matches.group("sha")
            self.repository = next_repo(self.repository, self.config.forked_from, sha)
            author = matches.group("author")
            date = matches.group("date")
            split = unindent(matches.group("message")).split("\n\n", 1)
            first, rest = (split[0], "") if len(split) == 1 else split
            if (
                first.startswith("Merge ")
                or first.startswith("Revert ")
                or first.startswith("Update ")
            ):
                continue
            parsed = re.match(COMMIT_REGEX, normalize_space(first))
            closes = tuple(sorted(set(parse_closes(first) + parse_closes(rest))))
            if parsed:
                entries.append(
                    LogEntry(
                        repository=self.repository,
                        sha=sha,
                        author=author,
                        date=date,
                        closes=closes,
                        **parsed.groupdict(),
                    )
                )
            else:
                entries.append(
                    LogEntry(
                        repository=self.repository,
                        sha=sha,
                        author=author,
                        date=date,
                        category="misc",
                        module=None,
                        message=first,
                        closes=closes,
                    )
                )
        return entries


def group_by_category(entries: list[LogEntry]) -> dict[str, list[LogEntry]]:
    grouped: dict[str, list[LogEntry]] = {}
    for entry in entries:
        if entry.category not in grouped:
            grouped[entry.category] = []
        grouped[entry.category].append(entry)
    return grouped


def group_by_message(entries: list[LogEntry]) -> dict[str, list[LogEntry]]:
    by_message: dict[str, list[LogEntry]] = {}
    for entry in entries:
        if entry.message not in by_message:
            by_message[entry.message] = []
        by_message[entry.message].append(entry)
    return by_message


def preferred_case(
    modules: Iterable[Optional[str]],
) -> dict[Optional[str], Optional[str]]:
    """Preferred case for module names is the one that has the most uppercase letters."""
    module_map: dict[Optional[str], Optional[str]] = {None: None}
    for module in modules:
        lower = module.lower() if module else None
        if lower not in module_map:
            # Don't have it yet.
            module_map[lower] = module
            continue

        current = module_map[lower]

        if current is None or module is None:
            continue

        # We have it. If the new one has more uppercase letters, use it.
        if sum(1 for c in module if c.isupper()) > sum(
            1 for c in current if c.isupper()
        ):
            module_map[module.lower()] = module
    return module_map


def group_by_module(
    entries: list[LogEntry],
) -> dict[Optional[str], dict[str, list[LogEntry]]]:
    by_module: dict[Optional[str], list[LogEntry]] = {}
    case = preferred_case(entry.module for entry in entries)
    for entry in entries:
        module = case[entry.module.lower() if entry.module else None]
        if module not in by_module:
            by_module[module] = []
        by_module[module].append(entry)
    return {module: group_by_message(entries) for module, entries in by_module.items()}


def format_closes(entry: LogEntry) -> str:
    message = ""
    for issue in entry.closes:
        message += f", closes [#{issue}]({entry.repository}/issues/{issue})"
    return message


MARKDOWN_REGEX = re.compile(
    r"`[^`]+`|\*\*[^\*]+\*\*|\*[^\*]+\*|_[^_]+_|~[^~]+~|\S+|\s+"
)
ITALIC_REGEX = re.compile(r"\*([^*]+)\*")
BOLD_REGEX = re.compile(r"\*\*([^*]+)\*\*")


def is_xml_tag(word: str) -> bool:
    return word.startswith("<") and word.endswith(">")


def escape(word: str) -> str:
    if word.startswith("`") and word.endswith("`"):
        return word
    if word == "*":
        return "\\*"
    if word == "<":
        return "&lt;"
    if word == ">":
        return "&gt;"
    if re.match(ITALIC_REGEX, word) and not re.match(BOLD_REGEX, word):
        return f"_{word[1:-1]}_"
    if "_" in word or is_xml_tag(word) or "::" in word:
        return f"`{word}`"
    if word.count("*") % 2:
        return word.replace("*", "\\*")
    return word


def format_message(entry: LogEntry) -> str:
    return "".join(escape(word) for word in re.findall(MARKDOWN_REGEX, entry.message))


def format_entry(entries: list[LogEntry]) -> str:
    if not entries:
        raise ValueError("No entries")
    shas = ", ".join(
        f"([{entry.sha[:8]}]({entry.repository}/commit/{entry.sha}){format_closes(entry)})"
        for entry in entries
    )
    return f"{format_message(entries[0])} {shas}"


def format_changelog(
    tag: tuple[str, str],
    groups: dict[str, dict[Optional[str], dict[str, list[LogEntry]]]],
    old_changelog: dict[str, changelog.ReleaseNotes],
) -> str:
    """
    <a name="v1.17.5"></a>

    ## v1.17.5 (2022-03-05)

    #### Bug Fixes

    - Update video API usage for newer libavcodec ([f5fabc2f](https://github.com/qTox/qTox/commit/f5fabc2fe24b6f01e47a527b982395a5305d31f6))
    - **Windows:**
    - Restrict non-default install directory permissions ([553bd47e](https://github.com/qTox/qTox/commit/553bd47e8171fd4f15e062e4faf734e32002f6fb))
    - Build NSIS installer in Unicode mode ([9f84184b](https://github.com/qTox/qTox/commit/9f84184ba815bfc892691fa611c6756721ba1333))
    - Define installer language before trying to access it ([1353fc93](https://github.com/qTox/qTox/commit/1353fc934ed70e9bfab3e50e42dba5eb139cd59e))

    #### Features

    - **Settings:** Add setting for hiding group join and leave system messages ([916e797c](https://github.com/qTox/qTox/commit/916e797c10d10ba556e9a3339353f1bd97663d15))
    - **UI:** Add UI For controlling group join and leave system messages setting ([423049db](https://github.com/qTox/qTox/commit/423049db50ffea14ec222e1a83ee976029a6afaf))
    - **chatlog:** Disable join and leave system messages based on setting ([ee0334ac](https://github.com/qTox/qTox/commit/ee0334acc55215ed8e94bae8fa4ff8976834af20))
    """
    version = tag[1].removeprefix(f"{git.RELEASE_BRANCH_PREFIX}/")
    tag_date = git_tag_date(tag[0]) if version == tag[1] else today()
    tag_message = old_changelog.get(version, None)
    lines = [
        f'<a name="{version}"></a>',
        "",
        f"## {version} ({tag_date})",
    ]
    if tag_message:
        if tag_message.header:
            lines.append("")
            lines.append(tag_message.header)
        if tag_message.notes:
            lines.append("")
            lines.append(tag_message.notes)
    for category, entries in groups.items():
        if category not in CATEGORIES:
            continue
        lines.append("")
        lines.append(f"#### {category_name(category)}")
        lines.append("")
        for module, module_entries in sorted(entries.items(), key=lambda x: x[0] or ""):
            if module is None:
                for entry in module_entries.values():
                    lines.append(f"- {format_entry(entry)}")
            elif len(module_entries) == 1:
                for entry in module_entries.values():
                    lines.append(f"- **{module}:** {format_entry(entry)}")
            else:
                lines.append(f"- **{module}:**")
                for entry in module_entries.values():
                    lines.append(f"  - {format_entry(entry)}")
    return "\n".join(lines)


def generate_changelog(
    old_changelog: dict[str, changelog.ReleaseNotes],
    parser: LogParser,
    cur_tag: tuple[str, str],
    prev_tag: tuple[str, str],
) -> Optional[str]:
    log = git_log(prev_tag[0], cur_tag[0])
    if not any(log):
        log = []
    groups = {
        k: group_by_module(v)
        for k, v in group_by_category(parser.parse_log(log)).items()
    }
    return format_changelog(cur_tag, groups, old_changelog)


def filter_str(strings: Iterable[Optional[str]]) -> Iterable[str]:
    return (s for s in strings if s)


def current_release_branch() -> list[tuple[str, str]]:
    head_ref = os.getenv("GITHUB_HEAD_REF")
    if head_ref and head_ref.startswith(f"{git.RELEASE_BRANCH_PREFIX}/"):
        return [("HEAD", head_ref)]
    branches = git.release_branches()
    if branches:
        return [(branches[0], branches[0])]
    return []


def main(config: Optional[Config] = None) -> None:
    if not config:
        config = parse_config(read_clog_toml())
    tags = current_release_branch() + [
        (t, t) for t in git.release_tags(with_rc=not config.production)
    ]
    # Ignore everything before and including some tag.
    # (+1 because we still need {after tag}...{tag}).
    if config.ignore_before:
        tags = tags[: tags.index((config.ignore_before, config.ignore_before)) + 1]
    old_changelog = changelog.parse(config.changelog)
    parser = LogParser(config)
    text = "\n\n".join(
        filter_str(
            generate_changelog(old_changelog, parser, t[0], t[1])
            for t in zip(tags, tags[1:])
        )
    )

    if config.changelog:
        with open(config.changelog, "w") as f:
            if text.strip():
                print(text, file=f)
    else:
        print(text)


if __name__ == "__main__":
    main(parse_args())
