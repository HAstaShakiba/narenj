# Narenj — a free Tangerine alternative for Windows and Linux

**Narenj** (نارنج) is a free, open-source, drag-and-drop file converter for **Windows**, **Linux** and
**macOS**: a Tangerine and FanDrop alternative for the systems those Mac apps don't run on.

Drag a file onto the wheel and drop it on a wedge: Narenj converts, compresses, trims or otherwise
processes video, audio, images, PDFs, documents, slides, spreadsheets, e-books, subtitles and
archives, and saves the result next to the original. Everything runs on your own computer, offline.

**[Download and install →](https://hastashakiba.github.io/narenj/)** · Windows installer · macOS
app · apt repository for Ubuntu and Debian · Homebrew

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Screenshot/wheel-convert-dark.png">
    <img src="Screenshot/wheel-convert-light.png" width="32%" alt="Narenj's Convert wheel">
  </picture>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Screenshot/wheel-tools-dark.png">
    <img src="Screenshot/wheel-tools-light.png" width="32%" alt="Narenj's Tools wheel">
  </picture>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Screenshot/wheel-actions-dark.png">
    <img src="Screenshot/wheel-actions-light.png" width="32%" alt="Narenj's Actions wheel">
  </picture>
</p>
<p align="center"><sub>The Convert, Tools and Actions wheels (Shift, Ctrl, Alt), with the tab bar above them;
they follow your light or dark theme</sub></p>

## Wheels

| Files | Convert | Tools |
|---|---|---|
| Video | MP4, MOV, MKV, WebM, GIF, animated WebP, MP3, SRT subtitles | Compress, Trim, Resize, Rotate, Mute, Frame, Normalize, Strip metadata |
| Audio | MP3, M4A, WAV, FLAC, OGG, Opus | Compress, Trim, Normalize, Mono, Strip metadata |
| Images (incl. SVG) | PNG, JPG, WebP, BMP, TIFF, ICO | Compress, Resize, Rotate, Grayscale, Strip metadata |
| PDF | PNG or JPG pages, DOCX, TXT | Compress |
| Documents (DOCX, DOC, ODT, RTF, TXT, MD, HTML) | PDF, DOCX, ODT, RTF, TXT, HTML, MD, EPUB | |
| Slides (PPTX, PPT, ODP) | PDF, PPTX, ODP | |
| Spreadsheets (XLSX, XLS, ODS, CSV) | PDF, XLSX, ODS, CSV | |
| EPUB | PDF, DOCX, TXT, HTML, MD | |
| Subtitles (SRT, VTT, ASS) | SRT, VTT, ASS | |
| Archives (ZIP, TAR, TAR.GZ/BZ2/XZ, GZ, RAR, 7z) | ZIP, TAR, TAR.GZ | Extract |

**Actions** for every file: Open, Reveal, Copy path, Trash, **Zip** (packs the files or folders),
plus Info for media and **Join** for several videos, songs or PDFs (end to end, in name order;
videos of different sizes are fitted to the first one's frame).

**Compress** keeps the file's format: a PNG stays a PNG (256 colours, transparency kept), a JPG,
WebP, MP4, WebM, MP3 or WAV stays what it was, only smaller; FLAC and TIFF are compressed
losslessly. Formats with no smaller form of themselves (BMP, ICO, SVG, AIFF) do not offer it.

A wheel never shows more than 8 wedges, Convert hides the file's own format, and a wedge only
appears when what it needs is installed:

| Needs | For | Linux | macOS (Homebrew) | Windows |
|---|---|---|---|---|
| ffmpeg | video, audio, images, subtitles | dependency | dependency | bundled |
| LibreOffice | documents, slides, spreadsheets, PDF → DOCX | `libreoffice-writer` etc. | `brew install --cask libreoffice` | [libreoffice.org](https://www.libreoffice.org/) |
| pandoc | Markdown, EPUB | recommended | dependency | [pandoc.org](https://pandoc.org/installing.html) |
| poppler | PDF pages, text, Join | recommended | dependency | bundled |
| Ghostscript | PDF Compress | recommended | dependency | [ghostscript.com](https://ghostscript.com/) |
| bsdtar or 7-Zip | RAR and 7z | `libarchive-tools` | built in | built in |

ZIP, TAR and GZIP need nothing: Narenj packs and unpacks them itself, and never writes outside the
folder it extracts into.

## Using it

- **Ctrl+Alt+N** opens the wheel; pressing it again closes it.
- The tabs above the wheel switch between Convert, Tools and Actions (hold a dragged file over one
  to switch); the × next to them closes Narenj.
- Drop a file on a wedge to run it, or on the centre to load the file and then click a wedge.
- Click the centre to pick files; drag the centre to move the wheel.
- Right-click for the menu: choose files, settings, glass level (clear / regular / tinted), cancel jobs, quit.
- Arrow keys pick a wedge, Enter applies it, Esc clears the selection.

## Settings

Right-click the wheel and choose **Settings…** (or press Ctrl+,):

- **Opens on**: the wheel shown when Narenj starts (Convert, Tools or Actions).
- **Glass**: how much of the desktop shows through.
- **Open and close the wheel**: click the shortcut and press a new key combination; Esc cancels,
  Backspace turns the shortcut off.

The wheel is a borderless, translucent window. A small GNOME Shell extension keeps it above other
windows on every workspace and reports the modifier keys held during a drag, since Wayland gives
apps no way to do either.

## Install

### From the apt repository (Ubuntu 22.04+ / Debian)

```sh
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://hastashakiba.github.io/narenj/narenj-archive-keyring.gpg | sudo tee /etc/apt/keyrings/narenj.gpg >/dev/null
echo "deb [signed-by=/etc/apt/keyrings/narenj.gpg] https://hastashakiba.github.io/narenj stable main" | sudo tee /etc/apt/sources.list.d/narenj.list
sudo apt update
sudo apt install narenj
narenj --setup                      # once per user: shortcut + extension
```

Log out and back in once so GNOME Shell loads the extension. Updates then arrive with `apt upgrade`.

### Windows 10 / 11

Download `narenj-<version>-setup.exe` from the [latest release](https://github.com/HAstaShakiba/narenj/releases/latest)
and run it; it installs for your user without admin rights and brings its own Python, GTK and ffmpeg.
**Ctrl+Alt+N** opens and closes the wheel (change it in Start menu › Narenj › Properties ›
Shortcut key). On Windows the wheel stays above other windows and reads Shift, Ctrl and Alt by
itself, so nothing else needs setting up.

### macOS app (Apple Silicon)

Download `narenj-<version>-macos.dmg` from the [latest release](https://github.com/HAstaShakiba/narenj/releases/latest),
open it and drag Narenj to Applications. The app is not signed with an Apple Developer ID, so the
first time macOS says it cannot verify it: open **System Settings › Privacy & Security** and click
**Open Anyway** (or run `xattr -dr com.apple.quarantine /Applications/Narenj.app`). Intel Macs use
Homebrew below.

### macOS (Homebrew)

```sh
brew tap hastashakiba/narenj https://github.com/HAstaShakiba/narenj
brew install narenj
narenj
```

Homebrew brings GTK, Python and ffmpeg. While Narenj runs, **Control+Option+N** shows and hides the
wheel, which floats above other windows on every Space; Shift, Control (or Command) and Option
switch wheels, also while dragging.

### Building the package yourself

```sh
./packaging/build-deb.sh            # writes dist/narenj_1.0.0_all.deb
sudo apt install ./dist/narenj_1.0.0_all.deb
narenj --setup                      # once per user: shortcut + extension
```

### From this checkout (current user only)

```sh
./install.sh
```

## Requirements

GNOME 42 or newer on Wayland, Python 3 with PyGObject, GTK 4.6+, libadwaita 1.1+, librsvg, ffmpeg.
On Ubuntu 22.04 the package pulls in everything it needs, including `fonts-inter`.

The UI uses Apple's San Francisco font when it is installed and otherwise
[Inter](https://rsms.me/inter/), its closest open counterpart. `fonts/InterVariable.ttf` is
Inter 4.1, distributed under the SIL Open Font License (see `fonts/LICENSE-Inter-OFL.txt`).
On Windows it uses Segoe UI. The Windows installer and the macOS app bundle FFmpeg 8.1.3, built from the
[ffmpeg.org](https://ffmpeg.org/download.html) sources by `packaging/build-ffmpeg.sh` with
x264, libvpx, Opus, LAME, Vorbis, libwebp and dav1d; that build is GPL licensed.

## Development

```sh
python3 -m unittest discover -s tests     # wheel contents + every ffmpeg wedge on generated media
```

GitHub Actions runs the same tests on every push and pull request.

## Releasing

1. Build and publish the apt repository: `./packaging/build-deb.sh 1.0.1 && ./packaging/publish-apt.sh`.
   It signs the repository with the "Narenj apt repository" GnuPG key and pushes it to the
   `gh-pages` branch (`--dry-run` builds it in `dist/apt-site` instead).
2. Tag the release: `git tag -a v1.0.1 -m "Narenj 1.0.1" && git push origin v1.0.1`.
   GitHub Actions tests it, builds the `.deb` and publishes the GitHub release.

Keep a backup of the signing key (`gpg --export-secret-keys "Narenj apt repository"`): without
it, updates can no longer be signed for people who already trust the repository.

## License

Narenj is released under the MIT License (see `LICENSE`). The bundled Inter font keeps its own
SIL Open Font License.

## Layout

| Path | Contents |
|---|---|
| `narenj.py` | The application |
| `gnome-extension/` | Shell helper for GNOME 42-44 |
| `gnome-extension-45/` | The same helper for GNOME 45+ (ES modules) |
| `packaging/` | `.deb` build script, launcher and desktop entry |
| `packaging/windows/` | Windows build (MSYS2) and Inno Setup installer |
| `Formula/` | Homebrew formula for macOS |
| `packaging/macos/` | macOS app (PyInstaller) and DMG build |
| `packaging/build-ffmpeg.sh` | The slim ffmpeg bundled on Windows and macOS (settings in `packaging/*/ffmpeg.sh`) |
| `install.sh` | Per-user install from the checkout |
| `tests/` | Wheel contents and every ffmpeg wedge on generated media |
| `icons/` | The wedges' symbolic icons, from GNOME's Adwaita theme (LGPL v3 / CC BY-SA 3.0) |
| `Screenshot/` | The wheel pictures above, drawn by `packaging/site/render-wheels.py` |
