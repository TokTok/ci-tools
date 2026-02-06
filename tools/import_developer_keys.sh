#!/bin/bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2026 The TokTok team

set -eux -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_DIR="$(dirname "$SCRIPT_DIR")/.github"

for key in "$GITHUB_DIR/keys"/*.asc; do
  gpg --import "$key"
done
