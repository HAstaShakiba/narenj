#!/usr/bin/env bash
# Builds dist/Narenj.app and dist/narenj-<version>-macos.dmg on a Mac with Homebrew:
#   packaging/macos/build-app.sh <python-with-gi> <ffmpeg-dir> <version>
# The app is ad-hoc signed only (no Apple Developer ID), so macOS asks once before opening it.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$1"; FFMPEG_DIR="$(cd "$2" && pwd)"; VERSION="$3"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$SRC"

# app icon from the SVG
ICONSET="$WORK/narenj.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
    rsvg-convert -w "$size" -h "$size" narenj.svg -o "$ICONSET/icon_${size}x${size}.png"
    rsvg-convert -w $((size * 2)) -h $((size * 2)) narenj.svg -o "$ICONSET/icon_${size}x${size}@2x.png"
done
iconutil -c icns -o "$WORK/narenj.icns" "$ICONSET"

"$PYTHON" -m venv --system-site-packages "$WORK/venv"
"$WORK/venv/bin/pip" install -q pyinstaller pyinstaller-hooks-contrib
NARENJ_FFMPEG_DIR="$FFMPEG_DIR" NARENJ_ICNS="$WORK/narenj.icns" NARENJ_VERSION="$VERSION" \
    "$WORK/venv/bin/pyinstaller" --noconfirm --distpath dist --workpath "$WORK/build" packaging/macos/narenj.spec

# a drag-to-Applications disk image
STAGE="$WORK/dmg"
mkdir -p "$STAGE"
cp -R dist/Narenj.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -quiet -volname Narenj -srcfolder "$STAGE" -ov -format UDZO "dist/narenj-$VERSION-macos.dmg"
du -sh dist/Narenj.app "dist/narenj-$VERSION-macos.dmg"
