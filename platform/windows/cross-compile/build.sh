#!/usr/bin/env bash

# SPDX-License-Identifier: MIT
# Copyright © 2017-2021 Maxim Biro <nurupo.contributions@gmail.com>
# Copyright © 2024-2025 The TokTok team.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

RUN_TESTS=0

while (($# > 0)); do
  case $1 in
    --project-name)
      PROJECT_NAME=$2
      shift 2
      ;;
    --src-dir)
      PROJECT_SRC_DIR=$2
      shift 2
      ;;
    --arch)
      ARCH=$2
      shift 2
      ;;
    --run-tests)
      RUN_TESTS=1
      shift
      ;;
    --build-type)
      BUILD_TYPE=$2
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      "Unexpected argument $1"
      exit 1
      ;;
  esac
done

# https://stackoverflow.com/questions/72978485/git-submodule-update-failed-with-fatal-detected-dubious-ownership-in-reposit
git config --global --add safe.directory '*'

# Check if we can git describe
git describe --tags --match 'v*'

# Common directory paths

PROJECT_BUILD_DIR="_build-$WINEARCH"
readonly PROJECT_BUILD_DIR
PROJECT_PREFIX_DIR="$(realpath install-prefix)"
readonly PROJECT_PREFIX_DIR
PROJECT_PACKAGE_DIR="$(realpath package-prefix)"
readonly PROJECT_PACKAGE_DIR

if [ -z "${ARCH:-}" ]; then
  echo "Error: No architecture was specified. Please specify either 'i686' or 'x86_64', case sensitive."
  exit 1
fi

if [[ "$ARCH" == "i686" ]]; then
  export WINE=/usr/lib/wine/wine
elif [[ "$ARCH" == "x86_64" ]]; then
  export WINE=/usr/lib/wine/wine64
else
  echo "Error: Incorrect architecture was specified. Please specify either 'i686' or 'x86_64', case sensitive."
  exit 1
fi

if [ -z "$PROJECT_SRC_DIR" ]; then
  echo "--src-dir must be specified"
fi

if [ -z "$BUILD_TYPE" ]; then
  echo "Error: No build type was specified. Please specify either 'Release' or 'Debug', case sensitive."
  exit 1
fi

if [[ "$BUILD_TYPE" != "Release" ]] && [[ "$BUILD_TYPE" != "Debug" ]]; then
  echo "Error: Incorrect build type was specified. Please specify either 'Release' or 'Debug', case sensitive."
  exit 1
fi

if [ -z "${PROJECT_NAME:-}" ]; then
  echo "Error: No project name was specified."
  exit 1
fi

BINARY_NAME="$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]')"

export PKG_CONFIG_PATH=/windows/lib64/pkgconfig

CMAKE_FLAGS=(
  -D CMAKE_TOOLCHAIN_FILE=/build/windows-toolchain.cmake
  -D CMAKE_LIBRARY_PATH=/windows/lib64
  -D CMAKE_PREFIX_PATH=/windows
  -D CMAKE_BUILD_TYPE=Release
  -D CMAKE_CROSSCOMPILING_EMULATOR="$WINE"
  -D CMAKE_C_COMPILER_LAUNCHER=ccache
  -D CMAKE_CXX_COMPILER_LAUNCHER=ccache
  -G Ninja
)

if [[ "$BUILD_TYPE" == "Debug" ]]; then
  CMAKE_FLAGS+=(-D CMAKE_EXE_LINKER_FLAGS="-mconsole")
fi

CMAKE_FLAGS+=("$@")

ccache --zero-stats

cmake "${CMAKE_FLAGS[@]}" -B "$PROJECT_BUILD_DIR" "$PROJECT_SRC_DIR"
cmake --build "$PROJECT_BUILD_DIR"

ccache --show-stats

mkdir -p "$PROJECT_PREFIX_DIR"
cp "$PROJECT_BUILD_DIR/$BINARY_NAME.exe" "$PROJECT_PREFIX_DIR"

# Always needed DLLs.
DLL_DEPS=(
  libstdc++-6.dll
  libwinpthread-1.dll
)

if [ "$ARCH" == "i686" ]; then
  DLL_DEPS+=(libgcc_s_dw2-1.dll)
elif [ "$ARCH" == "x86_64" ]; then
  DLL_DEPS+=(libgcc_s_seh-1.dll)
fi

# Add all the DLL dependencies from $SCRIPT_DIR/dll-deps to DLL_DEPS.
# Ignore lines starting with # and empty lines.
while IFS= read -r line; do
  if [ -n "$line" ] && [ "${line:0:1}" != "#" ]; then
    DLL_DEPS+=("$line")
  fi
done <"$SCRIPT_DIR/dll-deps"

# If tls/qopensslbackend.dll is in the DLL_DEPS, add the OpenSSL DLLs.
if [[ " ${DLL_DEPS[*]} " == *" tls/qopensslbackend.dll "* ]]; then
  if [ "$ARCH" == "i686" ]; then
    DLL_DEPS+=(
      libcrypto-3.dll
      libssl-3.dll
    )
  elif [ "$ARCH" == "x86_64" ]; then
    DLL_DEPS+=(
      libcrypto-3-x64.dll
      libssl-3-x64.dll
    )
  fi
fi

# Copy from /export to $PROJECT_PREFIX_DIR, but only the DLLs that are in DLL_DEPS.
for dll in "${DLL_DEPS[@]}"; do
  mkdir -p "$(dirname "$PROJECT_PREFIX_DIR/$dll")"
  cp "/export/$dll" "$PROJECT_PREFIX_DIR/$dll"
done

export WINEQT_QPA_PLATFORM='offscreen'
export WINEPREFIX="$PWD/$PROJECT_BUILD_DIR/.wine"

# Check if our main binary runs (just to see if any DLL errors happen early on).
# This also initialises the wine directory for tests (avoiding race conditions).
"$WINE" "$PROJECT_PREFIX_DIR/$BINARY_NAME.exe" --help

# Run tests
set +u
if [[ $RUN_TESTS -ne 0 ]]; then
  # Set up the environment for the tests (not needed for the main binary, where
  # we want to see if the prefix dir has everything we need).
  export WINEQT_PLUGIN_PATH='z:\export'
  export WINEPATH='z:\export;z:\windows\bin'
  ctest --test-dir "$PROJECT_BUILD_DIR" --parallel "$(nproc)" --output-on-failure
fi
set -u

# Strip
set +e
if [[ "$BUILD_TYPE" == "Release" ]]; then
  "$ARCH-w64-mingw32-strip" -s "$PROJECT_PREFIX_DIR"/*.exe
fi
"$ARCH-w64-mingw32-strip" -s "$PROJECT_PREFIX_DIR"/*.dll
"$ARCH-w64-mingw32-strip" -s "$PROJECT_PREFIX_DIR"/*/*.dll
set -e

if [[ "$BUILD_TYPE" == "Debug" ]]; then
  cp -r /debug_export/* "$PROJECT_PREFIX_DIR"
fi

# Create zip
pushd "$PROJECT_PREFIX_DIR"
zip "$BINARY_NAME-$ARCH-$BUILD_TYPE.zip" -r ./*
popd

# Create installer
if [[ "$BUILD_TYPE" == "Release" ]]; then
  mkdir -p "$PROJECT_PACKAGE_DIR"
  pushd "$PROJECT_PACKAGE_DIR"
  # The installer creation script expects all the files to be in $BINARY_NAME/*
  mkdir -p "$BINARY_NAME"
  cp -r "$PROJECT_PREFIX_DIR"/* "./$BINARY_NAME"
  rm ./"$BINARY_NAME"/*.zip

  cp -r "$PROJECT_SRC_DIR"/platform/windows/* .
  # Select the installer script for the correct architecture
  if [[ "$ARCH" == "i686" ]]; then
    grep -v '  SetRegView 64' "${BINARY_NAME}64.nsi" |
      sed -e 's/PROGRAMFILES64/PROGRAMFILES/g' |
      sed -e 's/FileRead /FileReadUTF16LE /g' \
        >"${BINARY_NAME}32.nsi"
    makensis "${BINARY_NAME}32.nsi"
  elif [[ "$ARCH" == "x86_64" ]]; then
    makensis "${BINARY_NAME}64.nsi"
  fi

  popd
fi

# dll check
# Create lists of all .exe and .dll files
find "$PROJECT_PREFIX_DIR" -iname '*.dll' >dlls
find "$PROJECT_PREFIX_DIR" -iname '*.exe' >exes

# Create a list of dlls that are loaded during the runtime (not listed in the PE
# import table, thus ldd doesn't print those).
echo >runtime-dlls
for path in iconengines imageformats kf6/sonnet platforms tls; do
  if [ -d "$PROJECT_PREFIX_DIR/$path" ]; then
    ls "$PROJECT_PREFIX_DIR/$path"/*.dll >>runtime-dlls
  fi
done

# Clean up any old file that may be here from previous runs.
rm -f dlls-required

# Create a tree of all required dlls
# Assumes all .exe files are directly in $PROJECT_PREFIX_DIR, not in subdirs
platform/windows/cross-compile/check-dlls "-j$(nproc)" \
  EXES="$(cat exes runtime-dlls)" \
  ARCH="$ARCH" \
  BUILD_DIR="$PROJECT_BUILD_DIR" \
  PREFIX_DIR="$PROJECT_PREFIX_DIR"

wc -l dlls-required

# pipefail breaks the checks below (I don't understand why - if someone does,
# please change this comment to explain).
set +o pipefail

# Check that no dll is missing. Ignore api-ms-win-*.dll, because they are
# symbolic names pointing at kernel32.dll, user32.dll, etc.
#
# See https://github.com/nurupo/mingw-ldd/blob/master/README.md#api-set-dlls
if grep -v 'api-ms-win-' dlls-required | grep -q 'not found'; then
  cat dlls-required
  echo "Error: Missing some dlls."
  exit 1
fi

# Check that no extra dlls get bundled
while IFS= read -r line; do
  if ! grep -q "$line" dlls-required; then
    echo "Error: extra dll included: $line. If this is a mistake and the dll is actually needed (e.g. it's loaded at runtime), please add it to the runtime dll list."
    exit 1
  fi
done <dlls

# Check that OpenAL is bundled. It is availabe from WINE, but not on Windows systems
if grep -q '/opt/wine-stable/lib/wine/i386-windows/openal32.dll' dlls-required; then
  cat dlls-required
  echo "Error: Missing OpenAL."
  exit 1
fi
