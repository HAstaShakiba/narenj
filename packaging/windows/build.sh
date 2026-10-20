#!/usr/bin/env bash
# Builds a self-contained Narenj folder for Windows, dist/windows/Narenj, from an MSYS2 UCRT64
# install. Run it from an MSYS2 UCRT64 shell after installing the packages listed in
# .github/workflows/ci.yml.
#
#   packaging/windows/build.sh <ffmpeg-dir>
#
# <ffmpeg-dir> holds ffmpeg.exe, ffprobe.exe and their DLLs (packaging/build-ffmpeg.sh).
#
# The folder mirrors the MSYS2 prefix (bin/, lib/, share/) because GLib, GObject
# introspection and Python all find their data relative to the DLL or executable.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
FFMPEG_DIR="$1"
PREFIX="${MINGW_PREFIX:-/ucrt64}"
OUT="$SRC/dist/windows/Narenj"
PYVER="$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"

rm -rf "$OUT"
mkdir -p "$OUT/bin" "$OUT/lib" "$OUT/share/narenj" "$OUT/share/icons" "$OUT/share/glib-2.0"

# Python, trimmed to what Narenj imports
cp "$PREFIX/bin/python.exe" "$PREFIX/bin/pythonw.exe" "$OUT/bin/"
cp -r "$PREFIX/lib/python$PYVER" "$OUT/lib/"
PYLIB="$OUT/lib/python$PYVER"
rm -rf "$PYLIB"/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3,pydoc_data,config-*}
find "$PYLIB/site-packages" -mindepth 1 -maxdepth 1 \
    ! -name 'gi' ! -name 'cairo' ! -iname 'pygobject*' ! -iname 'pycairo*' -exec rm -rf {} +
find "$PYLIB" -name '__pycache__' -prune -exec rm -rf {} +

# GObject introspection data, GTK's settings schemas and icons
cp -r "$PREFIX/lib/girepository-1.0" "$OUT/lib/"
cp -r "$PREFIX/share/glib-2.0/schemas" "$OUT/share/glib-2.0/"
cp -r "$PREFIX/share/icons/Adwaita" "$PREFIX/share/icons/hicolor" "$OUT/share/icons/"
# Windows draws its own cursors and GTK only needs the scalable and symbolic icons
find "$OUT/share/icons/Adwaita" -mindepth 1 -maxdepth 1 -type d \
    ! -name scalable ! -name symbolic -exec rm -rf {} +

# gdk-pixbuf loaders, with a cache template narenj.py fills in at startup
PIXBUF="lib/gdk-pixbuf-2.0/2.10.0"
mkdir -p "$OUT/$PIXBUF"
cp -r "$PREFIX/$PIXBUF/loaders" "$OUT/$PIXBUF/"
WINOUT="$(cygpath -m "$OUT")"
gdk-pixbuf-query-loaders "$OUT/$PIXBUF"/loaders/*.dll \
    | sed -e "s|$WINOUT|@ROOT@|g" -e "s|$(cygpath -m "$PREFIX")|@ROOT@|g" > "$OUT/$PIXBUF/loaders.cache.in"

# gdbus.exe runs the private session bus that keeps Narenj to one instance (for --toggle)
cp "$PREFIX/bin/gdbus.exe" "$OUT/bin/"

# Libraries loaded through introspection are not linked by anything, so seed them by name,
# then copy every DLL these files need from the MSYS2 prefix.
SEED=(libgtk-4-1.dll libadwaita-1-0.dll librsvg-2-2.dll libpangocairo-1.0-0.dll libgraphene-1.0-0.dll
      libharfbuzz-gobject-0.dll libgirepository-1.0-1.dll)
for dll in "${SEED[@]}"; do cp "$PREFIX/bin/$dll" "$OUT/bin/"; done
# ffmpeg first, so the encoder libraries its DLLs link to are collected with everything else
cp "$FFMPEG_DIR"/*.exe "$FFMPEG_DIR"/*.dll "$OUT/bin/"
mapfile -t BINARIES < <(find "$OUT" -type f \( -name '*.exe' -o -name '*.dll' -o -name '*.pyd' \))
PREFIX_WIN="$(cygpath -w "$PREFIX" | tr '[:upper:]' '[:lower:]')"
for _ in 1 2 3; do  # a few rounds pick up dependencies of newly copied DLLs
    ntldd -R "${BINARIES[@]}" 2>/dev/null | awk '{print $3}' | tr -d '\r' | sort -u | while read -r dep; do
        [ -n "$dep" ] || continue
        lower="$(echo "$dep" | tr '[:upper:]' '[:lower:]')"
        case "$lower" in "$PREFIX_WIN"\\bin\\*) ;; *) continue ;; esac
        name="$(basename "$(cygpath -u "$dep")")"
        [ -e "$OUT/bin/$name" ] || cp "$(cygpath -u "$dep")" "$OUT/bin/"
    done
    mapfile -t BINARIES < <(find "$OUT/bin" -type f -name '*.dll')
done

# Narenj itself
cp "$SRC/narenj.py" "$SRC/narenj.svg" "$OUT/share/narenj/"
cp "$SRC/packaging/windows/narenj.ico" "$OUT/"
cp "$SRC/LICENSE" "$OUT/LICENSE.txt"
[ -f "$FFMPEG_DIR/LICENSE.txt" ] && cp "$FFMPEG_DIR/LICENSE.txt" "$OUT/FFMPEG-LICENSE.txt"

du -sh "$OUT"
