#!/usr/bin/env bash
# Builds a slim, shared-library ffmpeg + ffprobe for the Windows bundle in an MSYS2 UCRT64 shell:
#   packaging/windows/build-ffmpeg.sh <out-dir>
#
# Ready-made static builds put every codec library into ffmpeg.exe and again into ffprobe.exe
# (~165 MB each). Here both share one set of DLLs, and the only external libraries are the
# encoders Narenj's wedges use (x264, libvpx, opus, lame, vorbis, webp) plus dav1d for AV1
# input; FFmpeg's own decoders still read nearly any file. The lavfi input device stays, as the
# tests generate their sample media with it.
set -euo pipefail

VERSION=8.1.3
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

curl -fsSL "https://ffmpeg.org/releases/ffmpeg-$VERSION.tar.xz" | tar -xJ -C "$WORK"
cd "$WORK/ffmpeg-$VERSION"

./configure --prefix="$WORK/install" \
    --enable-gpl --enable-shared --disable-static \
    --disable-doc --disable-debug --disable-ffplay --disable-network \
    --disable-indevs --enable-indev=lavfi --disable-outdevs \
    --disable-autodetect --enable-zlib \
    --enable-libx264 --enable-libvpx --enable-libopus --enable-libmp3lame --enable-libvorbis \
    --enable-libwebp --enable-libdav1d
make -j"$(nproc)"
make install

cp "$WORK/install/bin/"*.exe "$WORK/install/bin/"*.dll "$OUT/"
cp LICENSE.md "$OUT/LICENSE.txt"
strip "$OUT/"*.exe "$OUT/"*.dll
du -sh "$OUT"
