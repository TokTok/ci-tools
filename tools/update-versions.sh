#!/usr/bin/env bash

# If GITHUB_TOKEN or TOKEN_RELEASES are visible, error.
if [ -n "${GITHUB_TOKEN:-}" ] || [ -n "${TOKEN_RELEASES:-}" ]; then
  echo "GITHUB_TOKEN/TOKEN_RELEASES should not be visible in the version update script."
  exit 1
fi

# After the token check. We don't want to print tokens to the logs.
set -eux -o pipefail

VERSION=$1

# Strip suffixes (e.g. "-rc.1") from the version.
VERSION="${VERSION%-*}"

# Update VERSION in CMakeLists.txt.
sed -i "s/^  VERSION [0-9.]*$/  VERSION $VERSION/" CMakeLists.txt
