#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2019 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team

# Fail out on error
set -exuo pipefail

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

# https://stackoverflow.com/questions/72978485/git-submodule-update-failed-with-fatal-detected-dubious-ownership-in-reposit
git config --global --add safe.directory '*'

# Check if we can git describe
git describe --tags --match 'v*'

# directory paths
readonly BUILD_DIR="$(realpath .)"
readonly PROJECT_APP_DIR="$BUILD_DIR/$PROJECT_NAME.AppDir"

rm -f appimagetool-*.AppImage
wget "https://github.com/$(wget -q https://github.com/probonopd/go-appimage/releases/expanded_assets/continuous -O - | grep "appimagetool-.*-x86_64.AppImage" | head -n 1 | cut -d '"' -f 2)"
chmod +x appimagetool-*.AppImage

# https://github.com/probonopd/go-appimage/blob/fced8b8831039daa246ab355f4e2335074abc206/src/appimagetool/appdirtool.go#L400
# This line in the appimagetool breaks musl DNS lookups (looking for /EEE/resolv.conf).
./appimagetool-*.AppImage --appimage-extract
sed -i -e 's!/EEE!/etc!g' squashfs-root/usr/bin/appimagetool

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
  -B _build \
  "$@"
cmake --build _build
cmake --install _build --prefix "$PROJECT_NAME.AppDir/usr"

ccache --show-stats

export QTDIR=/opt/buildhome/qt
export LD_LIBRARY_PATH="/opt/buildhome/lib:/opt/buildhome/lib64:$QTDIR/lib"

# Copy offscreen/wayland plugins to the app dir.
mkdir -p "$PROJECT_APP_DIR/$QTDIR/plugins/platforms"
cp -r "$QTDIR/plugins/platforms/libqoffscreen.so" "$PROJECT_APP_DIR/$QTDIR/plugins/platforms/"
cp -r "$QTDIR/plugins/platforms/libqwayland-generic.so" "$PROJECT_APP_DIR/$QTDIR/plugins/platforms/"
# Copy the tls plugins to the app dir, needed for https connections.
cp -r "$QTDIR/plugins/tls/" "$PROJECT_APP_DIR/$QTDIR/plugins/"

squashfs-root/AppRun -s deploy "$PROJECT_APP_DIR"/usr/share/applications/*.desktop

# print all links not contained inside the AppDir
LD_LIBRARY_PATH='' find "$PROJECT_APP_DIR" -type f -exec ldd {} \; 2>&1 | grep '=>' | grep -v "$PROJECT_APP_DIR"

squashfs-root/AppRun "$PROJECT_APP_DIR"

APPIMAGE_FILE="$PROJECT_NAME-$(git rev-parse --short HEAD | head -c7)-$ARCH.AppImage"
sha256sum "$APPIMAGE_FILE" >"$APPIMAGE_FILE.sha256"
