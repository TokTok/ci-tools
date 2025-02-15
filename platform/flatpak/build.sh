#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2018-2021 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team

# Fail out on error
set -euxo pipefail

PROJECT_NAME=$1
ORG_NAME=$2

BINARY_NAME=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]')

# use multiple cores when building
export MAKEFLAGS="-j$(nproc)"
FLATPAK_DESCRIPTOR="$(dirname "$(realpath "$0")")/$ORG_NAME.$PROJECT_NAME.json"

# If $FLATPAK_BUILD is set, use it as the build directory
if [ -n "${FLATPAK_BUILD:-}" ]; then
  mkdir -p "$FLATPAK_BUILD"
  cd "$FLATPAK_BUILD"
fi

# Build the flatpak
flatpak-builder --ccache --disable-rofiles-fuse --install-deps-from=flathub --force-clean --repo="$BINARY_NAME-repo" _build-flatpak "$FLATPAK_DESCRIPTOR"

# Create a bundle for distribution
flatpak build-bundle "$BINARY_NAME-repo" "$PROJECT_NAME.flatpak" "$ORG_NAME.$PROJECT_NAME"

# Generate checksum.
sha256sum "$PROJECT_NAME.flatpak" >"$PROJECT_NAME.flatpak.sha256"

# If $FLATPAK_BUILD is set, copy the bundle to the build directory
if [ -n "${FLATPAK_BUILD:-}" ]; then
  cp "$PROJECT_NAME.flatpak" "/qtox"
  cp "$PROJECT_NAME.flatpak.sha256" "/qtox"
fi

rm -f .flatpak-builder/cache/.lock
