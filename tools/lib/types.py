# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team
from dataclasses import dataclass


@dataclass
class RepoSlug:
    owner: str
    name: str

    def __str__(self) -> str:
        return f"{self.owner}/{self.name}"
