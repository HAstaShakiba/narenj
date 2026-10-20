#!/bin/sh
# Builds dist/narenj_<version>_all.deb from this checkout.
set -e
VERSION="${1:-1.0.0}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$SRC/dist"
ROOT="$(mktemp -d)"
chmod 755 "$ROOT"  # mktemp makes it 0700, which would land in the package as the mode of /
trap 'rm -rf "$ROOT"' EXIT

install -Dm755 "$SRC/packaging/narenj.sh" "$ROOT/usr/bin/narenj"
install -Dm755 "$SRC/narenj.py" "$ROOT/usr/share/narenj/narenj.py"
install -Dm644 "$SRC/packaging/ir.narenj.Narenj.desktop" "$ROOT/usr/share/applications/ir.narenj.Narenj.desktop"
install -Dm644 "$SRC/narenj.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/ir.narenj.Narenj.svg"
for f in metadata.json extension.js; do
    install -Dm644 "$SRC/gnome-extension/$f" "$ROOT/usr/share/gnome-shell/extensions/narenj@narenj.ir/$f"
    install -Dm644 "$SRC/gnome-extension-45/$f" "$ROOT/usr/share/gnome-shell/extensions/narenj-gnome45@narenj.ir/$f"
done
install -Dm644 "$SRC/LICENSE" "$ROOT/usr/share/doc/narenj/copyright"
# the packaged copy runs through the wrapper's interpreter, not a hard-coded python3.10
sed -i '1s|.*|#!/usr/bin/python3|' "$ROOT/usr/share/narenj/narenj.py"

mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CONTROL
Package: narenj
Version: $VERSION
Section: video
Priority: optional
Architecture: all
Installed-Size: $(du -sk "$ROOT/usr" | cut -f1)
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-4.0 (>= 4.6),
 gir1.2-adw-1 (>= 1.1), gir1.2-rsvg-2.0, gir1.2-pango-1.0, ffmpeg, fonts-inter, adwaita-icon-theme
Recommends: gnome-shell (>= 42)
Maintainer: HAstaShakiba <HAstaShakiba@users.noreply.github.com>
Description: Drag-and-drop ffmpeg wheel for GNOME
 Drop a file on Narenj's wheel and pick a wedge to convert, compress, trim,
 resize or otherwise process it with ffmpeg, or to open, reveal, copy or
 trash it. Shift, Ctrl and Alt switch between the Convert, Tools and Actions
 wheels, even while dragging. A small GNOME Shell extension keeps the wheel
 above other windows; run "narenj --setup" once per user to enable it and the
 Ctrl+Alt+N shortcut (Narenj also does this on its first start).
CONTROL

mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$ROOT" "$OUT/narenj_${VERSION}_all.deb"
