FROM toxchat/qtox:wasm-builder AS builder

ENV PKG_CONFIG_PATH="/opt/buildhome/lib/pkgconfig"

COPY cmake /qtox/cmake/
COPY CMakeLists.txt /qtox/
COPY src /qtox/src/
RUN . "/opt/buildhome/emsdk/emsdk_env.sh" \
 && emcmake cmake \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_FIND_ROOT_PATH="/opt/buildhome;/opt/buildhome/qt" \
  -GNinja \
  -B_build-wasm \
  -H. \
 && cmake --build _build-wasm

COPY platform/wasm/_headers _site/
RUN cp \
  _build-wasm/qtloader.js \
  _build-wasm/qtlogo.svg \
  _build-wasm/citools.js \
  _build-wasm/citools.wasm \
  _site \
 && cp \
  _build-wasm/citools.html \
  _site/index.html

FROM alpine:3.21 AS venv

RUN apk add curl \
  gcc \
  linux-headers \
  musl-dev \
  py3-pip \
  py3-virtualenv \
  python3-dev

# Create a virtual environment for qtwasmserver.
# hadolint ignore=DL3013
RUN python3 -m venv /opt/buildhome/venv \
 && . /opt/buildhome/venv/bin/activate \
 && CFLAGS=-Wno-int-conversion pip3 install brotli httpcompressionserver netifaces \
 && curl -L https://raw.githubusercontent.com/qt/qtbase/refs/heads/dev/util/wasm/qtwasmserver/qtwasmserver.py -o /opt/buildhome/venv/bin/qtwasmserver.py \
 && chmod +x /opt/buildhome/venv/bin/qtwasmserver.py

FROM alpine:3.21

RUN apk add python3

COPY --from=venv /opt/buildhome/venv /opt/buildhome/venv
COPY --from=builder /qtox/_site /qtox/_site

ENV PORT=8000
WORKDIR /qtox/_site
CMD . /opt/buildhome/venv/bin/activate \
 && qtwasmserver.py \
 --cross-origin-isolation \
 --all-interfaces \
 --compress-never \
 --port "$PORT"
