#!/bin/sh
# Installs Narenj for the current user (app menu entry + "Open With" for media files).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$DIR/narenj.py"
mkdir -p "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps" "$HOME/.local/bin"
cp "$DIR/narenj.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/ir.narenj.Narenj.svg"
# Inter, the open stand-in for Apple's San Francisco (BlinkMacSystemFont)
mkdir -p "$HOME/.local/share/fonts"
cp "$DIR/fonts/InterVariable.ttf" "$HOME/.local/share/fonts/"
fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || true
ln -sf "$DIR/narenj.py" "$HOME/.local/bin/narenj"
cat > "$HOME/.local/share/applications/ir.narenj.Narenj.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Narenj
GenericName=Media Converter
Comment=Drop a file on the wheel to convert, compress or trim it with ffmpeg
Exec=$DIR/narenj.py %F
Icon=$HOME/.local/share/icons/hicolor/scalable/apps/ir.narenj.Narenj.svg
Terminal=false
Categories=AudioVideo;Video;AudioVideoEditing;
MimeType=video/mp4;video/quicktime;video/x-matroska;video/webm;video/x-msvideo;image/gif;audio/mpeg;audio/mp4;audio/x-wav;audio/flac;audio/ogg;image/png;image/jpeg;image/webp;image/svg+xml;
Keywords=ffmpeg;convert;compress;gif;mp3;video;audio;
StartupWMClass=ir.narenj.Narenj
DESKTOP
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
# -t: the user hicolor dir has no index.theme, so a plain update fails and leaves a stale cache
gtk-update-icon-cache -q -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

# Always on top: a tiny GNOME Shell extension pins the wheel above other windows
# (one copy per extension format: GNOME 42-44 and GNOME 45+)
for ext in gnome-extension:narenj@narenj.ir gnome-extension-45:narenj-gnome45@narenj.ir; do
    EXT_DIR="$HOME/.local/share/gnome-shell/extensions/${ext#*:}"
    mkdir -p "$EXT_DIR"
    cp "$DIR/${ext%%:*}/metadata.json" "$DIR/${ext%%:*}/extension.js" "$EXT_DIR/"
done

# Enable the extension and add the Ctrl+Alt+N toggle shortcut
"$DIR/narenj.py" --setup
echo "Narenj installed. Find it in the app grid, run: narenj, or press Ctrl+Alt+N."
