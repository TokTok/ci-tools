#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2019 by The qTox Project Contributors
# Copyright © 2024-2026 The TokTok team

# Fail out on error
set -exuo pipefail

# https://stackoverflow.com/questions/72978485/git-submodule-update-failed-with-fatal-detected-dubious-ownership-in-reposit
git config --global --add safe.directory '*'

# Ensure consistent file permissions
umask 022

# Support reproducible builds
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
  export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
fi

usage() {
  echo "$0 --src-dir SRC_DIR --project-name PROJECT_NAME [cmake args]"
  echo "Builds an app image in the CWD based off PROJECT_NAME installation at SRC_DIR"
}

while (($# > 0)); do
  case $1 in
    --project-name)
      PROJECT_NAME=$2
      shift 2
      ;;
    --src-dir)
      SRC_DIR=$2
      shift 2
      ;;
    --arch)
      ARCH=$2
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

if [ -z "${ARCH+x}" ]; then
  echo "--arch is a required argument"
  usage
  exit 1
fi

if [ -z "${SRC_DIR+x}" ]; then
  echo "--src-dir is a required argument"
  usage
  exit 1
fi

if [ -z "${PROJECT_NAME+x}" ]; then
  echo "--project-name is a required argument"
  usage
  exit 1
fi

# Check if we can git describe
git describe --tags --match 'v*'

# directory paths
readonly BUILD_DIR="$(realpath .)"
readonly PROJECT_APP_DIR="$BUILD_DIR/$PROJECT_NAME.AppDir"

# Pin appimagetool version for reproducibility
readonly APPIMAGE_TOOL_VERSION="940"
readonly APPIMAGE_TOOL_URL="https://github.com/probonopd/go-appimage/releases/download/continuous/appimagetool-$APPIMAGE_TOOL_VERSION-x86_64.AppImage"

rm -f appimagetool-*.AppImage
wget "$APPIMAGE_TOOL_URL" -O "appimagetool-$APPIMAGE_TOOL_VERSION-x86_64.AppImage"
chmod +x appimagetool-*.AppImage

# Extract tool to a isolated directory to avoid polluting the workspace/AppImage
readonly TOOL_EXTRACT_DIR="$BUILD_DIR/tool-extract"
rm -rf "$TOOL_EXTRACT_DIR"
"./appimagetool-$APPIMAGE_TOOL_VERSION-x86_64.AppImage" --appimage-extract
mv squashfs-root "$TOOL_EXTRACT_DIR"

# Patch the tool for musl compatibility.
# https://github.com/probonopd/go-appimage/blob/fced8b8831039daa246ab355f4e2335074abc206/src/appimagetool/appdirtool.go#L400
# This line in the appimagetool breaks musl DNS lookups (looking for /EEE/resolv.conf).
sed -i -e 's!/EEE!/etc!g' "$TOOL_EXTRACT_DIR/usr/bin/appimagetool"

export PKG_CONFIG_PATH=/opt/buildhome/lib/pkgconfig

ccache --zero-stats
ccache --show-config

echo "$PROJECT_APP_DIR"
cmake "$SRC_DIR" \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="/opt/buildhome/lib64/cmake;/opt/buildhome/qt/lib/cmake" \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,--build-id=none" \
  -B _build \
  "$@"
cmake --build _build
cmake --install _build --prefix "$PROJECT_NAME.AppDir/usr"

ccache --show-stats

# Normalize file permissions and timestamps for reproducibility
echo "Normalizing AppDir..."
find "$PROJECT_APP_DIR" -exec touch -h -d @"$SOURCE_DATE_EPOCH" {} +
find "$PROJECT_APP_DIR" -type d -exec chmod 0755 {} +
find "$PROJECT_APP_DIR" -type f -perm /0111 -exec chmod 0755 {} +
find "$PROJECT_APP_DIR" -type f ! -perm /0111 -exec chmod 0644 {} +

export QTDIR=/opt/buildhome/qt
export LD_LIBRARY_PATH="/opt/buildhome/lib:/opt/buildhome/lib64:$QTDIR/lib"

# Copy offscreen/wayland plugins to the app dir.
mkdir -p "$PROJECT_APP_DIR/$QTDIR/plugins/platforms"
cp -r "$QTDIR/plugins/platforms/libqoffscreen.so" "$PROJECT_APP_DIR/$QTDIR/plugins/platforms/"
cp -r "$QTDIR/plugins/platforms/libqwayland-generic.so" "$PROJECT_APP_DIR/$QTDIR/plugins/platforms/"
# Copy the tls plugins to the app dir, needed for https connections.
cp -r "$QTDIR/plugins/tls/" "$PROJECT_APP_DIR/$QTDIR/plugins/"

"$TOOL_EXTRACT_DIR/AppRun" -s deploy "$PROJECT_APP_DIR"/usr/share/applications/*.desktop

# print all links not contained inside the AppDir
LD_LIBRARY_PATH='' find "$PROJECT_APP_DIR" -type f -exec ldd {} \; 2>&1 | grep '=>' | grep -v "$PROJECT_APP_DIR"

# appimagetool (go-appimage) passes -fstime to mksquashfs, which conflicts with
# SOURCE_DATE_EPOCH environment variable.
(
  unset SOURCE_DATE_EPOCH
  "$TOOL_EXTRACT_DIR/AppRun" "$PROJECT_APP_DIR"
)

# Deterministic filename
readonly SHA="$(git rev-parse --short HEAD | head -c7)"
APPIMAGE_FILE="$PROJECT_NAME-$SHA-$ARCH.AppImage"
sha256sum "$APPIMAGE_FILE" >"$APPIMAGE_FILE.sha256"
