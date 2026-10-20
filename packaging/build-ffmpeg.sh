#!/usr/bin/env bash
# Builds a slim, shared-library ffmpeg + ffprobe for the Windows and macOS bundles:
#   packaging/build-ffmpeg.sh <out-dir> <platform-file>
# <platform-file> (packaging/windows/ffmpeg.sh or packaging/macos/ffmpeg.sh) sets
# PLATFORM_FLAGS and defines collect(), which copies the build into <out-dir>. Keeping them
# apart gives each platform its own CI cache, so a change for one does not rebuild the other.
#
# Ready-made static builds put every codec library into ffmpeg.exe and again into ffprobe.exe
# (~165 MB each). Here both share one set of libraries, and the only external ones are the
# encoders Narenj's wedges use (x264, libvpx, opus, lame, vorbis, webp) plus dav1d for AV1
# input; FFmpeg's own decoders still read nearly any file. The lavfi input device stays, as the
# tests generate their sample media with it.
#
# With ccache on PATH, compiling goes through it (CI keeps its cache between builds).
set -euo pipefail

VERSION=8.1.3
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
PLATFORM_FLAGS=()
# shellcheck source=/dev/null
source "$2"
# a fixed path next to <out-dir>: ccache matches sources by path, so a random temp dir would miss
WORK="$(dirname "$OUT")/.ffmpeg-build"
rm -rf "$WORK" && mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

curl -fsSL "https://ffmpeg.org/releases/ffmpeg-$VERSION.tar.xz" | tar -xJ -C "$WORK"
cd "$WORK/ffmpeg-$VERSION"

CC_FLAGS=()
if command -v ccache >/dev/null; then
    CC_FLAGS=(--cc="ccache $CC_NAME")
fi

./configure --prefix="$WORK/install" "${CC_FLAGS[@]}" "${PLATFORM_FLAGS[@]}" \
    --enable-gpl --enable-shared --disable-static \
    --disable-doc --disable-debug --disable-ffplay --disable-network \
    --disable-indevs --enable-indev=lavfi --disable-outdevs \
    --disable-autodetect --enable-zlib \
    --enable-libx264 --enable-libvpx --enable-libopus --enable-libmp3lame --enable-libvorbis \
    --enable-libwebp --enable-libdav1d
make -j"$(getconf _NPROCESSORS_ONLN)"
make install

collect "$WORK/install" "$OUT"
cp LICENSE.md "$OUT/LICENSE.txt"
du -sh "$OUT"
command -v ccache >/dev/null && ccache --show-stats || true
