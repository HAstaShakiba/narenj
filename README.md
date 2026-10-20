# Narenj

A drag-and-drop ffmpeg wheel for GNOME and Windows, inspired by [Tangerine](https://tangerineformac.com/) and FanDrop on macOS.

Drag a file onto the wheel and drop it on a wedge: Narenj converts, compresses, trims or otherwise
processes it with ffmpeg and saves the result next to the original. Everything runs locally.

<p align="center">
  <img src="Screenshot/convert.png" width="32%" alt="Convert wheel">
  <img src="Screenshot/tools.png" width="32%" alt="Tools wheel">
  <img src="Screenshot/actions.png" width="32%" alt="Actions wheel">
</p>
<p align="center"><sub>The Convert, Tools and Actions wheels (Shift, Ctrl, Alt) in the dark theme</sub></p>

## Wheels

| Wheel | Video | Audio | Image |
|---|---|---|---|
| Convert | MP4, MOV, MKV, WebM, GIF, animated WebP, MP3, SRT subtitles | MP3, M4A, WAV, FLAC, OGG, Opus | PNG, JPG, WebP, BMP, TIFF, ICO |
| Tools | Compress, Trim, Resize, Rotate, Mute, Frame, Normalize, Strip metadata | Compress, Trim, Normalize, Mono, Strip metadata | Compress, Resize, Rotate, Grayscale, Strip metadata |
| Actions | Open, Reveal in Files, Copy path, Info, Trash, Join | same | Open, Reveal, Copy path, Info, Trash |

A wheel never shows more than 8 wedges, and Convert hides the file's own format. SVG files count as
images (their tools write PNG). **Join** puts several videos or songs end to end, in name order;
videos of different sizes are fitted to the first one's frame. **SRT** pulls out a video's first
subtitle track.

## Using it

- **Ctrl+Alt+N** opens the wheel; pressing it again closes it.
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
On Windows it uses Segoe UI. The Windows installer bundles a static ffmpeg build from
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds), which is GPL licensed; its source is
available from [ffmpeg.org](https://ffmpeg.org/download.html).

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
| `install.sh` | Per-user install from the checkout |
| `tests/` | Wheel contents and every ffmpeg wedge on generated media |
| `Screenshot/` | The images above |
