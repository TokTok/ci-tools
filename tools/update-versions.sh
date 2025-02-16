#!/usr/bin/env bash

set -eux -o pipefail

VERSION=$1

# Strip suffixes (e.g. "-rc.1") from the version.
VERSION="${VERSION%-*}"

# Update VERSION in CMakeLists.txt.
sed -i "s/^  VERSION [0-9.]*$/  VERSION $VERSION/" CMakeLists.txt
