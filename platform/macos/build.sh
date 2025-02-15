#!/bin/bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2016-2021 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team

# Fail out on error
set -eux -o pipefail

MACOS_BUILD_TYPE="dist"
MACOS_ARCH="arm64"
MACOS_VERSION="12.0"

GIT_ROOT=$(git rev-parse --show-toplevel)
DEP_PREFIX="$GIT_ROOT/third_party/deps"

usage() {
  echo "Usage: $0 --project-name <project-name> [options]"
  echo "Options:"
  echo "  --project-name <project-name>   Name of the project (required)"
  echo "  --build-type <build-type>       Build type (user or dist)"
  echo "  --dep-prefix <dep-prefix>       Dependency prefix (default: third_party/deps)"
  echo "  --arch <arch>                   Architecture (arm64 or x86_64)"
  echo "  --macos-version <macos-version> macOS version (default: 12.0)"
  echo "  --help, -h                      Show this help message"
}

while (($# > 0)); do
  case $1 in
    --project-name)
      PROJECT_NAME=$2
      shift 2
      ;;
    --build-type)
      MACOS_BUILD_TYPE=$2
      shift 2
      ;;
    --dep-prefix)
      DEP_PREFIX=$2
      shift 2
      ;;
    --arch)
      MACOS_ARCH=$2
      shift 2
      ;;
    --macos-version)
      MACOS_VERSION=$2
      shift 2
      ;;
    --help | -h)
      usage
      exit 1
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unexpected argument $1"
      usage
      exit 1
      ;;
  esac
done

if [ -z "${PROJECT_NAME+x}" ]; then
  echo "--project-name is a required argument"
  usage
  exit 1
fi

readonly BIN_NAME="$PROJECT_NAME-$MACOS_ARCH-$MACOS_VERSION.dmg"

if [ "$MACOS_BUILD_TYPE" == "user" ]; then
  CMAKE=cmake
  PREFIX_PATH="$(brew --prefix qt@6)"
elif [ "$MACOS_BUILD_TYPE" == "dist" ]; then
  CMAKE="$DEP_PREFIX/qt/bin/qt-cmake"
  PREFIX_PATH="$DEP_PREFIX;$(brew --prefix qt@6)"
else
  echo "Unknown arg $MACOS_BUILD_TYPE"
  exit 1
fi

# Build project.
ccache --zero-stats

# Explicitly include with -isystem to avoid warnings from system headers.
# CMake will use -I instead of -isystem, so we need to set it manually.
"$CMAKE" \
  -DCMAKE_CXX_FLAGS="-isystem/usr/local/include" \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOS_VERSION" \
  -DCMAKE_PREFIX_PATH="$PREFIX_PATH" \
  -GNinja \
  -B_build \
  "$@" \
  .
cmake --build _build
ctest --output-on-failure --parallel "$(sysctl -n hw.ncpu)" --test-dir _build
cmake --install _build
cp "_build/$PROJECT_NAME.dmg" "$BIN_NAME"

ccache --show-stats

# Check if the binary exists.
if [[ ! -s "$BIN_NAME" ]]; then
  echo "There's no $BIN_NAME!"
  exit 1
fi

# Create a sha256 checksum.
shasum -a 256 "$BIN_NAME" >"$BIN_NAME".sha256
