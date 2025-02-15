#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2017-2019 The qTox Project Contributors
# Copyright © 2025 The TokTok team

# Generates $BINARY_NAME.ico from $BINARY_NAME.svg
#
# Usage: ./generate-icon.sh <binary-name>
#   binary-name: name of the binary, e.g. "qtox"
#
# Dependencies:
#   base64 8.25
#   ImageMagick 7.0.4
#   icoutils 0.31.0

set -eux -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GIT_ROOT=$(git rev-parse --show-toplevel)

BINARY_NAME=${1:-}

# Default to the git directory name.
if [ -z "$BINARY_NAME" ]; then
  BINARY_NAME=$(basename "$GIT_ROOT" | tr '[:upper:]' '[:lower:]')
fi

cd "$SCRIPT_DIR"

# Black, gray and transparent colors from Windows 16-color palette
base64 -d <<<R0lGODlhBAABAPEAAAAAAAAAAICAgMDAwCH5BAEAAAAALAAAAAAEAAEAAAIDjAYFADs= >pal.gif
# Generate 32 bpp images
magick -background none -depth 8 "$GIT_ROOT/resources/images/icons/$BINARY_NAME.svg" "${BINARY_NAME}_256_256_32.png"
magick "${BINARY_NAME}_256_256_32.png" -resize 64x64 "${BINARY_NAME}_64_64_32.png"
magick "${BINARY_NAME}_256_256_32.png" -resize 48x48 "${BINARY_NAME}_48_48_32.png"
magick "${BINARY_NAME}_256_256_32.png" -resize 32x32 "${BINARY_NAME}_32_32_32.png"
magick "${BINARY_NAME}_256_256_32.png" -resize 24x24 "${BINARY_NAME}_24_24_32.png"
magick "${BINARY_NAME}_256_256_32.png" -resize 16x16 "${BINARY_NAME}_16_16_32.png"
# Generate 8 bpp images
magick "${BINARY_NAME}_48_48_32.png" +dither "png8:${BINARY_NAME}_48_48_8.png"
magick "${BINARY_NAME}_32_32_32.png" +dither "png8:${BINARY_NAME}_32_32_8.png"
magick "${BINARY_NAME}_16_16_32.png" +dither "png8:${BINARY_NAME}_16_16_8.png"
# Generate 1 bpp images
magick "${BINARY_NAME}_32_32_8.png" +dither -remap pal.gif "png8:${BINARY_NAME}_32_32_1.png"
magick "${BINARY_NAME}_16_16_8.png" +dither -remap pal.gif "png8:${BINARY_NAME}_16_16_1.png"
# Hack for Windows XP file properties page
magick "${BINARY_NAME}_256_256_32.png" -modulate 99.5 -strip "${BINARY_NAME}_256_256_32.png"
magick "${BINARY_NAME}_64_64_32.png" -modulate 99.5 "${BINARY_NAME}_64_64_32.png"
magick "${BINARY_NAME}_48_48_32.png" -modulate 99.5 "${BINARY_NAME}_48_48_32.png"
magick "${BINARY_NAME}_32_32_32.png" -modulate 99.5 "${BINARY_NAME}_32_32_32.png"
magick "${BINARY_NAME}_24_24_32.png" -modulate 99.5 "${BINARY_NAME}_24_24_32.png"
magick "${BINARY_NAME}_16_16_32.png" -modulate 99.5 "${BINARY_NAME}_16_16_32.png"
# Build .ico file from .png images
icotool -c -t 32 \
  "${BINARY_NAME}_32_32_1.png" \
  "${BINARY_NAME}_16_16_1.png" \
  "${BINARY_NAME}_48_48_8.png" \
  "${BINARY_NAME}_32_32_8.png" \
  "${BINARY_NAME}_16_16_8.png" \
  --raw="${BINARY_NAME}_256_256_32.png" \
  "${BINARY_NAME}_64_64_32.png" \
  "${BINARY_NAME}_48_48_32.png" \
  "${BINARY_NAME}_32_32_32.png" \
  "${BINARY_NAME}_24_24_32.png" \
  "${BINARY_NAME}_16_16_32.png" \
  >"$BINARY_NAME.ico"
rm -f pal.gif "$BINARY_NAME"_*.png
# Show debug information
icotool -l "$BINARY_NAME.ico"
