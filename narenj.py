#!/usr/bin/python3.10
"""Narenj: a drag-and-drop ffmpeg wheel for GNOME and Windows.

Drop a file on the wheel, pick a wedge, and ffmpeg does the rest.
Three wheels, like Tangerine/FanDrop: Convert (Shift), Tools (Ctrl), Actions (Alt).
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    # The Windows build is a self-contained folder: <root>/bin/pythonw.exe, ffmpeg.exe and GTK's
    # DLLs, <root>/lib for typelibs and gdk-pixbuf loaders. gdk-pixbuf needs absolute loader
    # paths, so its cache ships as a template that is filled in for wherever Narenj was installed.
    _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(sys.executable)))
    _LOADERS = os.path.join(_ROOT, "lib", "gdk-pixbuf-2.0", "2.10.0", "loaders.cache.in")
    if os.path.exists(_LOADERS):
        _cache = os.path.join(os.environ.get("LOCALAPPDATA", _ROOT), "Narenj", "loaders.cache")
        os.makedirs(os.path.dirname(_cache), exist_ok=True)
        with open(_LOADERS, encoding="utf-8") as _src, open(_cache, "w", encoding="utf-8") as _dst:
            _dst.write(_src.read().replace("@ROOT@", _ROOT.replace("\\", "/")))
        os.environ["GDK_PIXBUF_MODULE_FILE"] = _cache
        os.environ["PATH"] = os.path.join(_ROOT, "bin") + os.pathsep + os.environ.get("PATH", "")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("PangoCairo", "1.0")
gi.require_version("Rsvg", "2.0")
import cairo  # noqa: E402
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango, PangoCairo, Rsvg  # noqa: E402

APP_ID = "ir.narenj.Narenj"
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
# keep ffmpeg/ffprobe from flashing a console window on Windows
NO_CONSOLE = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}
DEBUG = bool(os.environ.get("NARENJ_DEBUG"))
SETTINGS_PATH = os.path.join(GLib.get_user_config_dir(), "narenj", "settings.json")
# the same helper in GNOME 42-44's and GNOME 45+'s extension formats; Shell loads the one that fits
EXTENSION_UUIDS = ("narenj@narenj.ir", "narenj-gnome45@narenj.ir")
SHORTCUT_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/narenj/"
SHORTCUT = "<Control><Alt>n"

VIDEO, AUDIO, IMAGE, FOLDER, OTHER = "video", "audio", "image", "folder", "other"
CONVERT, TOOLS, ACTIONS = "convert", "tools", "actions"
MODES = (CONVERT, TOOLS, ACTIONS)
MODE_TITLES = {CONVERT: "Convert", TOOLS: "Tools", ACTIONS: "Actions"}
MODE_KEYS = {CONVERT: "Shift", TOOLS: "Ctrl", ACTIONS: "Alt"}
MODE_ACCENT = {
    CONVERT: ((1.00, 0.70, 0.28), (0.95, 0.36, 0.12)),
    TOOLS: ((1.00, 0.78, 0.30), (0.93, 0.52, 0.00)),
    ACTIONS: ((1.00, 0.55, 0.50), (0.91, 0.26, 0.33)),
}

EXT_KIND = {}
for _kind, _exts in {
    VIDEO: "mp4 mov mkv webm avi wmv flv m4v mpg mpeg ts mts 3gp gif",
    AUDIO: "mp3 m4a wav flac ogg oga opus aac aiff aif wma amr",
    IMAGE: "jpg jpeg png webp bmp tif tiff svg",
}.items():
    for _e in _exts.split():
        EXT_KIND[_e] = _kind
EXT_ALIAS = {"jpeg": "jpg", "tif": "tiff", "aif": "aiff", "oga": "ogg"}


def file_ext(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return EXT_ALIAS.get(ext, ext)


def kind_of(path):
    if os.path.isdir(path):
        return FOLDER
    return EXT_KIND.get(os.path.splitext(path)[1].lower().lstrip("."), OTHER)


class Action:
    """One wedge. `spec` maps a file kind to (output ext or None for same, ffmpeg args)."""

    def __init__(self, id, label, hint, spec=None, handler=None, suffix=None, prompt=None):
        self.id = id
        self.label = label
        self.hint = hint
        self.spec = spec or {}
        self.handler = handler
        self.suffix = suffix
        self.prompt = prompt

    def accepts(self, kind):
        return kind in self.spec


def _x264(crf, preset="medium"):
    # yuv420p needs even dimensions; odd-sized GIFs and phone clips would fail otherwise
    return ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-crf", str(crf),
            "-preset", preset, "-pix_fmt", "yuv420p"]


# JPEG has no alpha: paint transparent PNG/SVG pixels white instead of black
FLATTEN = "color=white,format=rgb24[bg];[bg][0:v]scale2ref[bg][fg];[bg][fg]overlay=shortest=1"
GIF_FILTER = "fps=12,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse"
AV = (VIDEO, AUDIO)
ALL_FILES = (VIDEO, AUDIO, IMAGE, FOLDER, OTHER)

WHEELS = {
    CONVERT: [
        Action("mp4", "MP4", "H.264", {VIDEO: ("mp4", _x264(23) + ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"])}),
        Action("mov", "MOV", "QuickTime", {VIDEO: ("mov", _x264(20) + ["-c:a", "aac", "-b:a", "192k"])}),
        Action("mkv", "MKV", "remux", {VIDEO: ("mkv", ["-map", "0", "-c", "copy"])}),
        Action("webm", "WebM", "VP9", {VIDEO: ("webm", ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1", "-c:a", "libopus", "-b:a", "128k"])}),
        Action("gif", "GIF", "480p · 12fps", {VIDEO: ("gif", ["-vf", GIF_FILTER, "-loop", "0", "-an"])}),
        Action("mp3", "MP3", "V2", {k: ("mp3", ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]) for k in AV}),
        # a video's soundtrack goes to MP3; the other audio targets are for audio files, keeping
        # the video wheel at 8 alongside animated WebP and subtitles
        Action("m4a", "M4A", "AAC", {AUDIO: ("m4a", ["-vn", "-c:a", "aac", "-b:a", "192k"])}),
        Action("wav", "WAV", "PCM", {AUDIO: ("wav", ["-vn", "-c:a", "pcm_s16le"])}),
        Action("flac", "FLAC", "lossless", {AUDIO: ("flac", ["-vn", "-c:a", "flac"])}),
        Action("ogg", "OGG", "Vorbis", {AUDIO: ("ogg", ["-vn", "-c:a", "libvorbis", "-q:a", "5"])}),
        Action("opus", "Opus", "128k", {AUDIO: ("opus", ["-vn", "-c:a", "libopus", "-b:a", "128k"])}),
        Action("png", "PNG", "lossless", {IMAGE: ("png", ["-frames:v", "1"])}),
        Action("jpg", "JPG", "q 95", {IMAGE: ("jpg", ["-filter_complex", FLATTEN, "-frames:v", "1", "-q:v", "2"])}),
        Action("webp", "WebP", "still or animated", {
            IMAGE: ("webp", ["-frames:v", "1", "-c:v", "libwebp", "-quality", "85"]),
            VIDEO: ("webp", ["-vf", "fps=12,scale=480:-1:flags=lanczos", "-c:v", "libwebp", "-quality", "75",
                             "-loop", "0", "-an"]),
        }),
        Action("srt", "SRT", "subtitles", {VIDEO: ("srt", ["-map", "0:s:0", "-c:s", "srt"])}),
        Action("bmp", "BMP", "bitmap", {IMAGE: ("bmp", ["-frames:v", "1"])}),
        Action("tiff", "TIFF", "print", {IMAGE: ("tiff", ["-frames:v", "1"])}),
        # Windows icons are at most 256 px a side
        Action("ico", "ICO", "icon", {IMAGE: ("ico", [
            "-vf", "scale='min(256,iw)':'min(256,ih)':force_original_aspect_ratio=decrease", "-frames:v", "1"])}),
    ],
    TOOLS: [
        Action("compress", "Compress", "smaller file", {
            VIDEO: ("mp4", _x264(28, "slow") + ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]),
            AUDIO: ("mp3", ["-vn", "-c:a", "libmp3lame", "-b:a", "96k"]),
            IMAGE: ("jpg", ["-filter_complex", FLATTEN, "-frames:v", "1", "-q:v", "6"]),
        }, suffix="compressed"),
        Action("trim", "Trim", "start → end", {VIDEO: (None, []), AUDIO: (None, [])},
               suffix="trim", prompt="trim"),
        Action("resize", "Resize", "max 1280px", {
            VIDEO: (None, ["-vf", "scale='min(1280,iw)':-2", "-c:a", "copy"]),
            IMAGE: (None, ["-vf", "scale='min(1280,iw)':-1", "-frames:v", "1"]),
        }, suffix="1280"),
        Action("rotate", "Rotate", "90° clockwise", {
            VIDEO: (None, ["-vf", "transpose=1", "-c:a", "copy"]),
            IMAGE: (None, ["-vf", "transpose=1", "-frames:v", "1"]),
        }, suffix="rotated"),
        Action("gray", "Grayscale", "black & white", {
            IMAGE: (None, ["-vf", "hue=s=0", "-frames:v", "1"]),
        }, suffix="gray"),
        Action("mute", "Mute", "drop audio", {VIDEO: (None, ["-an", "-c:v", "copy"])}, suffix="muted"),
        Action("frame", "Frame", "best thumbnail", {VIDEO: ("png", ["-vf", "thumbnail", "-frames:v", "1"])}, suffix="frame"),
        Action("normalize", "Normalize", "EBU R128", {
            VIDEO: (None, ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy"]),
            AUDIO: (None, ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]),
        }, suffix="normalized"),
        Action("mono", "Mono", "1 channel", {
            AUDIO: (None, ["-ac", "1"]),
        }, suffix="mono"),
        Action("strip", "Strip", "metadata", {
            VIDEO: (None, ["-map", "0", "-map_metadata", "-1", "-c", "copy"]),
            AUDIO: (None, ["-map_metadata", "-1", "-c", "copy"]),
            IMAGE: (None, ["-map_metadata", "-1", "-frames:v", "1"]),
        }, suffix="clean"),
    ],
    ACTIONS: [
        Action("open", "Open", "default app", {k: None for k in ALL_FILES}, handler="open"),
        Action("reveal", "Reveal", "in Files", {k: None for k in ALL_FILES}, handler="reveal"),
        Action("copy", "Copy path", "clipboard", {k: None for k in ALL_FILES}, handler="copy"),
        Action("info", "Info", "ffprobe", {k: None for k in (VIDEO, AUDIO, IMAGE)}, handler="info"),
        Action("trash", "Trash", "move to bin", {k: None for k in ALL_FILES}, handler="trash"),
        Action("join", "Join", "files end to end", {VIDEO: ("mp4", []), AUDIO: (None, [])},
               handler="join", suffix="joined"),
    ],
}


# GIFs count as video but carry no audio or subtitle track
AUDIO_ONLY_IDS = {"mp3", "m4a", "wav", "flac", "ogg", "opus", "mute", "normalize", "mono", "srt"}


def wheel_items(mode, kind, ext):
    items = [a for a in WHEELS[mode] if a.accepts(kind)]
    if mode == CONVERT:
        items = [a for a in items if a.id != ext]
    if ext == "gif":
        items = [a for a in items if a.id not in AUDIO_ONLY_IDS]
    if ext == "svg":
        items = [a for a in items if a.id != "strip"]
    return items


def output_path(src, action, kind):
    ext, _ = action.spec[kind]
    # ffmpeg can read SVG but not write it, so same-format tools hand back a PNG
    ext = ext or ("png" if file_ext(src) == "svg" else os.path.splitext(src)[1].lstrip(".")) or "out"
    folder = os.path.dirname(src)
    stem = os.path.splitext(os.path.basename(src))[0]
    if action.suffix:
        stem = f"{stem}-{action.suffix}"
    candidate = os.path.join(folder, f"{stem}.{ext}")
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem} {n}.{ext}")
        n += 1
    return candidate


def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def default_mode():
    mode = load_settings().get("default_mode")
    return mode if mode in MODES else CONVERT


def shortcut_settings():
    """The Gio.Settings holding Narenj's toggle shortcut, registering it first if needed."""
    keys = _gsettings("org.gnome.settings-daemon.plugins.media-keys")
    if not keys:
        return None
    if SHORTCUT_PATH not in keys.get_strv("custom-keybindings"):
        desktop_setup()
    return _gsettings("org.gnome.settings-daemon.plugins.media-keys.custom-keybinding", SHORTCUT_PATH)


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def win32_keep_on_top(window):
    """Windows lets an app pin itself above other windows; GNOME needs the Shell extension."""
    try:
        import ctypes
        gi.require_version("GdkWin32", "4.0")
        from gi.repository import GdkWin32
        hwnd = GdkWin32.Win32Surface.get_handle(window.get_surface())
        hwnd_topmost, swp_nosize_nomove_noactivate = -1, 0x0001 | 0x0002 | 0x0010
        ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(hwnd_topmost),
                                          0, 0, 0, 0, swp_nosize_nomove_noactivate)
    except (ImportError, ValueError, OSError, AttributeError) as e:
        if DEBUG:
            print("could not keep the wheel on top:", e, flush=True)


def win32_modifiers():
    """Shift/Ctrl/Alt held right now, as Gdk masks. Windows reports them even while another
    app (Explorer) owns the drag."""
    import ctypes
    held = ctypes.windll.user32.GetAsyncKeyState
    mods = 0
    for vk, mask in ((0x10, Gdk.ModifierType.SHIFT_MASK), (0x11, Gdk.ModifierType.CONTROL_MASK),
                     (0x12, Gdk.ModifierType.ALT_MASK)):
        if held(vk) & 0x8000:
            mods |= int(mask)
    return mods


def _gsettings(schema, path=None):
    source = Gio.SettingsSchemaSource.get_default()
    if not source or not source.lookup(schema, True):
        return None  # not GNOME, or that part of it is missing
    return Gio.Settings.new_with_path(schema, path) if path else Gio.Settings.new(schema)


def desktop_setup(force=False):
    """Per-user GNOME settings a system package must not touch: the Ctrl+Alt+N toggle and
    the always-on-top Shell extension. `force` also repoints an existing shortcut at this
    copy of Narenj. Returns what changed."""
    changed = []
    shell = _gsettings("org.gnome.shell")
    if shell:
        enabled = shell.get_strv("enabled-extensions")
        missing = [uuid for uuid in EXTENSION_UUIDS if uuid not in enabled]
        if missing:
            shell.set_strv("enabled-extensions", enabled + missing)
            changed.append("extension")
    keys = _gsettings("org.gnome.settings-daemon.plugins.media-keys")
    if keys:
        paths = keys.get_strv("custom-keybindings")
        if force or SHORTCUT_PATH not in paths:
            shortcut = _gsettings("org.gnome.settings-daemon.plugins.media-keys.custom-keybinding", SHORTCUT_PATH)
            command = shutil.which("narenj") or os.path.abspath(sys.argv[0])
            shortcut.set_string("name", "Narenj")
            shortcut.set_string("command", f"{command} --toggle")
            if SHORTCUT_PATH not in paths:
                shortcut.set_string("binding", SHORTCUT)
                keys.set_strv("custom-keybindings", paths + [SHORTCUT_PATH])
            changed.append("shortcut")
    Gio.Settings.sync()
    return changed


def probe(path):
    if not FFPROBE:
        return {}
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries",
             "format=duration,size,bit_rate,format_long_name:"
             "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
             "-of", "json", path],
            capture_output=True, text=True, timeout=15, **NO_CONSOLE,
        )
        return json.loads(out.stdout or "{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}


def rasterize_svg(path):
    """Render an SVG to a PNG at least 1024 px wide with librsvg, since many ffmpeg builds
    (all Windows ones) cannot read SVG. Returns the PNG's path."""
    folder = os.path.join(tempfile.gettempdir(), "narenj-svg")
    os.makedirs(folder, exist_ok=True)
    stat = os.stat(path)
    key = f"{os.path.abspath(path)}|{stat.st_mtime_ns}|{stat.st_size}".encode()
    png = os.path.join(folder, hashlib.sha1(key).hexdigest() + ".png")
    if not os.path.exists(png):
        handle = Rsvg.Handle.new_from_file(path)
        ok, w, h = handle.get_intrinsic_size_in_pixels()
        if not ok or not w or not h:
            w, h = 1024, 1024
        zoom = max(1.0, 1024 / w)
        width, height = max(1, round(w * zoom)), max(1, round(h * zoom))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        viewport = Rsvg.Rectangle()
        viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, width, height
        handle.render_document(cairo.Context(surface), viewport)
        surface.write_to_png(png)
    return png


def ffmpeg_command(src, kind, action, dst, extra_in=(), extra_out=()):
    """The ffmpeg call for one wedge; progress goes to stdout as key=value lines."""
    _, args = action.spec[kind]
    if file_ext(src) == "svg":
        src = rasterize_svg(src)
    return [FFMPEG, "-hide_banner", "-nostdin", "-y", *extra_in, "-i", src, *args, *extra_out,
            "-progress", "pipe:1", "-nostats", dst]


def has_stream(path, codec_type):
    return any(s.get("codec_type") == codec_type for s in probe(path).get("streams", []))


def natural_key(path):
    """clip2 before clip10."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", os.path.basename(path))]


def join_command(files, kind, dst):
    """Concatenate files end to end. Videos are scaled and padded to the first one's frame, so
    clips of any size join; audio is resampled to 48 kHz stereo."""
    infos = [probe(f) for f in files]
    with_audio = all(any(s.get("codec_type") == "audio" for s in i.get("streams", [])) for i in infos)
    graph, labels = [], []
    if kind == VIDEO:
        first = next(s for s in infos[0].get("streams", []) if s.get("codec_type") == "video")
        w, h = first["width"] // 2 * 2, first["height"] // 2 * 2
        for i in range(len(files)):
            graph.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                         f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{i}]")
            labels.append(f"[v{i}]")
            if with_audio:
                graph.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
                labels.append(f"[a{i}]")
        graph.append(f"{''.join(labels)}concat=n={len(files)}:v=1:a={int(with_audio)}" + ("[v][a]" if with_audio else "[v]"))
        out = ["-map", "[v]", "-c:v", "libx264", "-crf", "23", "-preset", "medium", "-pix_fmt", "yuv420p"]
        if with_audio:
            out += ["-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
        out += ["-movflags", "+faststart"]
    else:
        for i in range(len(files)):
            graph.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
            labels.append(f"[a{i}]")
        graph.append(f"{''.join(labels)}concat=n={len(files)}:v=0:a=1[a]")
        out = ["-map", "[a]"]
    inputs = [arg for f in files for arg in ("-i", f)]
    return [FFMPEG, "-hide_banner", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(graph), *out,
            "-progress", "pipe:1", "-nostats", dst]


def probe_duration(path):
    try:
        return float(probe(path).get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        return 0.0


def parse_time(text):
    """'1:02:03.5', '2:10' or '75' -> seconds."""
    seconds = 0.0
    for part in text.strip().split(":"):
        seconds = seconds * 60 + float(part or 0)
    return seconds


def format_time(seconds):
    seconds = max(0, seconds)
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    frac = seconds - int(seconds)
    tail = f"{s:02d}" + (f".{int(frac * 10)}" if frac >= 0.1 else "")
    return f"{h}:{m:02d}:{tail}" if h else f"{m}:{tail}"


def human_size(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ---------------------------------------------------------------- wheel drawing



# BlinkMacSystemFont is Apple's San Francisco, which only ships (and is only licensed) on
# Apple devices; use it if someone has it, else Inter, the open font closest to it
FONT = "SF Pro Text, Inter Variable, Inter, Segoe UI Variable Text, Segoe UI, Sans"


def _rgb(cr, c, a=1.0):
    cr.set_source_rgba(c[0], c[1], c[2], a)


def _layout(cr, text, font, width=None, align=Pango.Alignment.CENTER):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription.from_string(font))
    layout.set_alignment(align)
    if width:
        layout.set_width(int(width * Pango.SCALE))
        layout.set_ellipsize(Pango.EllipsizeMode.END)
    layout.set_text(text, -1)
    return layout


# Proportions measured from Tangerine's wheel, relative to the tiles' outer radius
TILE_INNER = 0.395   # where the tiles start
CENTER_DISC = 0.32   # the round label in the middle
TILE_CORNER = 0.085  # tile corner radius
TILE_GAP = 0.05      # even gap between tiles
HOT_SCALE = 1.0      # Tangerine's hot tile does not grow
SPIN_FROM = math.radians(-40)  # FanDrop-style turn-in when the wheel opens


def wheel_geometry(w, h, open_t):
    cx, cy = w / 2, h / 2
    full = (min(w, h) / 2 - 18) / HOT_SCALE
    inner = full * TILE_INNER
    outer = inner + (full - inner) * open_t
    return cx, cy, inner, outer


ICONS = {
    **{k: "video-x-generic" for k in ("mp4", "mov", "mkv", "webm")},
    "gif": "media-playback-start",
    **{k: "audio-x-generic" for k in ("mp3", "m4a", "wav", "flac", "ogg", "opus")},
    **{k: "image-x-generic" for k in ("png", "jpg", "webp", "bmp", "tiff")},
    "compress": "view-restore",
    "trim": "edit-cut",
    "resize": "view-fullscreen",
    "rotate": "object-rotate-right",
    "gray": "color-select",
    "mute": "audio-volume-muted",
    "frame": "camera-photo",
    "normalize": "multimedia-volume-control",
    "mono": "audio-headphones",
    "strip": "edit-clear-all",
    "open": "document-open",
    "reveal": "folder-open",
    "copy": "edit-copy",
    "info": "dialog-information",
    "trash": "user-trash",
    "join": "insert-link",
}
ICON_ROOTS = [os.path.join(d, "icons", "Adwaita", "scalable") for d in GLib.get_system_data_dirs()]
_icon_cache = {}


def icon_surface(name, size, scale):
    """Adwaita symbolic icon rendered once into an alpha mask, so it can be tinted any colour."""
    key = (name, size, scale)
    if key not in _icon_cache:
        surface = None
        for folder in ("actions", "mimetypes", "status", "devices", "places", "apps", "categories"):
            path = next((p for p in (os.path.join(root, folder, f"{name}-symbolic.svg") for root in ICON_ROOTS)
                         if os.path.exists(p)), None)
            if path:
                try:
                    handle = Rsvg.Handle.new_from_file(path)
                    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size * scale, size * scale)
                    viewport = Rsvg.Rectangle()
                    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, size * scale, size * scale
                    handle.render_document(cairo.Context(surface), viewport)
                    surface.set_device_scale(scale, scale)
                except GLib.Error:
                    surface = None
                break
        _icon_cache[key] = surface
    return _icon_cache[key]


def _draw_icon(cr, name, x, y, size, color, alpha, scale):
    surface = icon_surface(name, size, scale) if name else None
    if surface:
        _rgb(cr, color, alpha)
        cr.mask_surface(surface, x - size / 2, y - size / 2)


def wedge_path(cr, cx, cy, ri, ro, a0, a1, gap, radius):
    """Annular sector with even gaps; stroking it 2*radius wide with round joins rounds the corners."""
    d = gap / 2 + radius
    ri2, ro2 = ri + radius, ro - radius
    so = math.asin(min(1.0, d / ro2))
    si = math.asin(min(1.0, d / ri2))
    mid = (a0 + a1) / 2
    cr.new_path()
    cr.arc(cx, cy, ro2, min(a0 + so, mid), max(a1 - so, mid))
    cr.arc_negative(cx, cy, ri2, max(a1 - si, mid), min(a0 + si, mid))
    cr.close_path()


def _rounded_shape(cr, radius):
    """Fill + wide round stroke of the current (shrunk) path = the rounded tile."""
    cr.fill_preserve()
    cr.set_line_width(radius * 2)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.stroke()


def _edge(cr, make_path, radius, source, width):
    """Only the outer `width` px of a rounded pane, painted with `source`, as a pattern."""
    cr.push_group()
    make_path()
    cr.set_source(source)
    _rounded_shape(cr, radius)
    cr.set_operator(cairo.OPERATOR_DEST_OUT)
    cr.set_source_rgba(0, 0, 0, 1)  # DEST_OUT erases by source alpha; a fading source would leave residue
    make_path()
    cr.fill_preserve()
    cr.set_line_width(max(0.1, radius * 2 - width * 2))
    cr.stroke()
    cr.set_operator(cairo.OPERATOR_OVER)
    return cr.pop_group()


def _glass(cr, make_path, radius, body, alpha, rim, top, bottom):
    """One pane of glass: a faint tinted body plus a bright hairline rim that fades downwards.

    Each layer is composited once, so overlapping fill and stroke never seam through the translucency.
    """
    cr.push_group()
    make_path()
    cr.set_source(body)
    _rounded_shape(cr, radius)
    cr.pop_group_to_source()
    cr.paint_with_alpha(alpha)

    shine = cairo.LinearGradient(0, top, 0, bottom)
    shine.add_color_stop_rgba(0, 1, 1, 1, 1)
    shine.add_color_stop_rgba(1, 1, 1, 1, 0.25)
    cr.set_source(_edge(cr, make_path, radius, shine, 1.2))
    cr.paint_with_alpha(rim)


def _caps(cr, text, size, width=None, weight="Bold"):
    """Small, letter-spaced uppercase label like Tangerine's."""
    layout = _layout(cr, text.upper(), f"{FONT} {weight} {size:.1f}", width)
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_letter_spacing_new(int(0.5 * Pango.SCALE)))
    layout.set_attributes(attrs)
    return layout


def _label_room(theta, chord, depth, height):
    """Widest horizontal block of `height` that fits a tile whose radial axis points at `theta`.

    Across the tile the block spans w*|sin| + h*|cos| (limited by the chord), along it
    w*|cos| + h*|sin| (limited by the tile's depth).
    """
    c, sn = abs(math.cos(theta)), abs(math.sin(theta))
    room = []
    if sn > 1e-3:
        room.append((chord - height * c) / sn)
    if c > 1e-3:
        room.append((depth - height * sn) / c)
    return max(0.0, min(room))


def _fit_caps(cr, text, size, room, extra_height=0, weight="Bold", min_size=6.0):
    """Shrink a caps label until it fits `room(height)`; ellipsize only at the smallest size."""
    while True:
        layout = _caps(cr, text, size, None, weight)
        _, ext = layout.get_pixel_extents()
        allowed = room(ext.height + extra_height)
        if ext.width <= allowed or size <= min_size:
            break
        size = max(min_size, size * max(0.8, allowed / ext.width) - 0.1)
    if ext.width > allowed:
        layout = _caps(cr, text, size, allowed, weight)
    return layout


def _vertical(top_rgb, bottom_rgb, top, bottom):
    grad = cairo.LinearGradient(0, top, 0, bottom)
    grad.add_color_stop_rgb(0, *top_rgb)
    grad.add_color_stop_rgb(1, *bottom_rgb)
    return grad


def _show_text(cr, layout, x, y, color, alpha):
    _, logical = layout.get_pixel_extents()
    cr.move_to(x - logical.width / 2 - logical.x, y - logical.height / 2)
    _rgb(cr, color, alpha)
    PangoCairo.show_layout(cr, layout)
    return logical.height


# Golden Gate's Appearance slider, from clear to tinted: how much of the desktop shows through
GLASS_LEVELS = {"clear": 1.6, "regular": 1.0, "tinted": 0.4}


def palette(dark, glass="regular"):
    """Glass tints and how see-through they are at the chosen glass level; no shadows (like Tangerine)."""
    if dark:
        pal = {"plate": (0, 0, 0, 0.50), "tint_top": (0.32, 0.32, 0.36), "tint_bottom": (0.14, 0.14, 0.17),
               "tile_alpha": 0.65, "center_alpha": 0.83, "rim": 0.30, "text": (1, 1, 1)}
    else:
        pal = {"plate": (1, 1, 1, 0.46), "tint_top": (1, 1, 1), "tint_bottom": (0.90, 0.92, 0.95),
               "tile_alpha": 0.64, "center_alpha": 0.85, "rim": 0.85, "text": (0x0b / 255, 0x0b / 255, 0x0b / 255)}
    k = GLASS_LEVELS.get(glass, 1.0)

    def see(a):
        return max(0.05, 1 - (1 - a) * k)

    pal["plate"] = (*pal["plate"][:3], see(pal["plate"][3]))
    pal["tile_alpha"] = see(pal["tile_alpha"])
    pal["center_alpha"] = see(pal["center_alpha"])
    return pal


def draw_wheel(cr, w, h, s, dark):
    """Paint the wheel. `s` carries mode, items, hover, files, open_t, drag_active, busy, progress, flash."""
    pal = palette(dark, getattr(s, "glass", "regular"))
    scale = getattr(s, "scale", 1)
    cx, cy, r0, R = wheel_geometry(w, h, s.open_t)
    accent = MODE_ACCENT[s.mode][1]
    fg = pal["text"]
    has_file = bool(s.files)
    items = s.items
    n = len(items)
    hovered_item = items[s.hover] if s.hover is not None and 0 <= s.hover < n else None
    top, bottom = cy - R, cy + R

    # the plate: a barely tinted disc with a light-catching rim, and a warm glow while dragging
    plate = R + 10
    if s.drag_active:
        glow = cairo.RadialGradient(cx, cy, plate, cx, cy, plate + 16)
        glow.add_color_stop_rgba(0, *accent, 0.45)
        glow.add_color_stop_rgba(1, *accent, 0)
        cr.set_source(glow)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.arc(cx, cy, plate + 16, 0, 2 * math.pi)
        cr.new_sub_path()
        cr.arc(cx, cy, plate, 0, 2 * math.pi)
        cr.fill()
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)
    cr.set_source_rgba(*pal["plate"])
    cr.arc(cx, cy, plate, 0, 2 * math.pi)
    cr.fill()
    rim = cairo.LinearGradient(0, cy - plate, 0, cy + plate)
    rim.add_color_stop_rgba(0, 1, 1, 1, pal["rim"])
    rim.add_color_stop_rgba(1, 1, 1, 1, pal["rim"] * 0.3)
    cr.set_source(rim)
    cr.set_line_width(1.2)
    cr.arc(cx, cy, plate - 0.6, 0, 2 * math.pi)
    cr.stroke()

    # tiles: rounded glass sectors with even gaps; the hot one turns solid accent
    ri = r0
    step = 2 * math.pi / max(n, 1)
    full = R / s.open_t if s.open_t else R
    radius = full * TILE_CORNER
    spin = getattr(s, "spin", 0.0)
    body = _vertical(pal["tint_top"], pal["tint_bottom"], top, bottom)
    order = sorted(range(n), key=lambda i: items[i] is hovered_item)  # hot wedge on top
    for i in order:
        item = items[i]
        hovered = item is hovered_item
        grow = HOT_SCALE if hovered else 1.0
        a0 = -math.pi / 2 + i * step - step / 2 + spin
        a1 = a0 + step
        if n == 1:
            a0, a1 = -math.pi / 2 + 0.02, 3 * math.pi / 2 - 0.02
        gap = full * TILE_GAP

        def tile_path(a0=a0, a1=a1, grow=grow, gap=gap):
            wedge_path(cr, cx, cy, ri * grow, R * grow, a0, a1, gap, radius)

        if hovered:
            _glass(cr, tile_path, radius, cairo.SolidPattern(*accent), 0.95, 0.35, top, bottom)
        else:
            _glass(cr, tile_path, radius, body, pal["tile_alpha"], pal["rim"], top, bottom)

        if s.open_t < 0.5:
            continue
        mid = (a0 + a1) / 2
        rl = (ri + (R - ri) * 0.56) * grow  # a little outward, where the tile is wider
        lx, ly = cx + math.cos(mid) * rl, cy + math.sin(mid) * rl
        color = (1, 1, 1) if hovered else fg
        # room inside the tile, keeping clear of its rounded corners
        pad = radius * 0.4
        chord = 2 * rl * math.sin(min(step, math.pi) / 2) - gap - 2 * pad
        depth = (R - ri) * grow - 2 * pad

        def room(height, mid=mid, chord=chord, depth=depth):
            return _label_room(mid, chord, depth, height)

        if s.mode == CONVERT:
            # formats are just their name, big and bold
            label = _fit_caps(cr, item.label, full * (0.066 if n <= 8 else 0.058), room)
            _show_text(cr, label, lx, ly, color, 1.0)
        else:
            icon = round(full * 0.09)
            label = _fit_caps(cr, item.label, full * (0.043 if n <= 8 else 0.039), room, icon + 5)
            lh = label.get_pixel_extents()[1].height
            _draw_icon(cr, ICONS.get(item.id), lx, ly - lh / 2 - 3, icon, color, 1.0, scale)
            _show_text(cr, label, lx, ly + icon / 2 + 2, color, 1.0)

    if n == 0:
        cr.push_group()
        cr.arc(cx, cy, R, 0, 2 * math.pi)
        cr.arc_negative(cx, cy, ri, 2 * math.pi, 0)
        cr.set_source(body)
        cr.fill()
        cr.pop_group_to_source()
        cr.paint_with_alpha(pal["tile_alpha"] * 0.6)

    # centre button: the most opaque pane, so its text always reads
    rc = full * CENTER_DISC
    _glass(cr, lambda: (cr.new_path(), cr.arc(cx, cy, 0.01, 0, 2 * math.pi)), rc,
           _vertical(pal["tint_top"], pal["tint_bottom"], cy - rc, cy + rc), pal["center_alpha"], pal["rim"],
           cy - rc, cy + rc)
    if s.hover == -1:
        _rgb(cr, accent)
        cr.set_line_width(2.5)
        cr.arc(cx, cy, rc - 1.5, 0, 2 * math.pi)
        cr.stroke()

    # running jobs: an accent ring just inside the centre button
    if s.busy:
        cr.set_line_width(3.5)
        _rgb(cr, accent, 0.18)
        cr.arc(cx, cy, rc - 6, 0, 2 * math.pi)
        cr.stroke()
        _rgb(cr, accent)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.arc(cx, cy, rc - 6, -math.pi / 2, -math.pi / 2 + 2 * math.pi * max(0.02, s.progress))
        cr.stroke()
        cr.set_line_cap(cairo.LINE_CAP_BUTT)

    if s.flash:
        title, sub = s.flash
    elif hovered_item and (has_file or s.drag_active):
        title, sub = hovered_item.label, hovered_item.hint
    elif n == 0 and (has_file or s.drag_active):
        title, sub = f"No {MODE_TITLES[s.mode]}", "for this file"
    elif s.busy:
        title = "Working"
        sub = f"{int(s.progress * 100)}%" + (f" · {s.busy} jobs" if s.busy > 1 else "")
    elif has_file:
        name = os.path.basename(s.files[0])
        title = name if len(s.files) == 1 else f"{len(s.files)} files"
        sub = f"{MODE_TITLES[s.mode]} · " + (s.kind if len(s.files) == 1 else f"{name} + {len(s.files) - 1} more")
    elif s.drag_active:
        title, sub = MODE_TITLES[s.mode], "drop on a wedge"
    else:
        title, sub = "Drop a file", f"{MODE_TITLES[s.mode]} · or click"
    # Tangerine's centre: one short uppercase word, with our status line under it
    width = rc * 1.55
    t = _fit_caps(cr, title, full * 0.05, lambda _h: width, weight="Semibold")
    u = _layout(cr, sub, f"{FONT} {full * 0.037:.1f}", width)
    th = t.get_pixel_extents()[1].height
    uh = u.get_pixel_extents()[1].height
    _show_text(cr, t, cx, cy - uh / 2 - 1, fg, 1.0)
    _show_text(cr, u, cx, cy + th / 2 + 1, fg, 0.75)


LINK = int(Gdk.DragAction.LINK)
DRAG_ANY = Gdk.DragAction.COPY | Gdk.DragAction.MOVE | Gdk.DragAction.LINK | Gdk.DragAction.ASK
ACTION_MODE = {
    int(Gdk.DragAction.MOVE): CONVERT,   # Shift
    int(Gdk.DragAction.COPY): TOOLS,     # Ctrl
    int(Gdk.DragAction.ASK): ACTIONS,    # Alt
}


# SwiftUI .spring(response: 0.55, dampingFraction: 0.65), FanDrop's animation
SPRING_RESPONSE, SPRING_DAMPING, SPRING_SETTLE = 0.55, 0.65, 0.9


def spring(t):
    omega = 2 * math.pi / SPRING_RESPONSE
    damped = omega * math.sqrt(1 - SPRING_DAMPING ** 2)
    decay = math.exp(-SPRING_DAMPING * omega * t)
    return 1 - decay * (math.cos(damped * t) + SPRING_DAMPING * omega / damped * math.sin(damped * t))


class Wheel(Gtk.DrawingArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.mode = default_mode()
        self.files = []
        self.kind = VIDEO
        self.ext = ""
        self.items = []
        self.hover = None
        self.open_t = 0.88
        self.spin = 0.0
        self.drag_active = False
        self.drag_sample = None
        self.busy = 0
        self.progress = 0.0
        self.flash = None
        self.glass = load_settings().get("glass", "regular")
        self._flash_timer = 0
        self._anim = None
        self._tick = 0
        self._move_from = None
        self._moved = False
        self._key_poll = 0
        self._shell_keys = True
        self._polled_mode = None
        self._reset_drag_keys()
        self.set_size_request(440, 440)
        self.set_focusable(True)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.set_draw_func(self._draw)
        self.connect("resize", lambda *_: self.update_input_region())

        # accept every action so the compositor's modifier-driven choice reaches us (see _track_drag_keys)
        drop = Gtk.DropTarget.new(Gdk.FileList, DRAG_ANY)
        drop.set_preload(True)
        drop.connect("enter", self._on_drag_motion)
        drop.connect("motion", self._on_drag_motion)
        drop.connect("leave", self._on_drag_leave)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_pointer_motion)
        motion.connect("leave", lambda _c: self._set_hover(None))
        self.add_controller(motion)

        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)

        # pressing the centre disc and dragging moves the borderless window
        move = Gtk.GestureDrag()
        move.connect("drag-begin", self._on_move_begin)
        move.connect("drag-update", self._on_move_update)
        self.add_controller(move)

        menu_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        menu_click.connect("pressed", self._on_menu_click)
        self.add_controller(menu_click)

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL | Gtk.EventControllerScrollFlags.DISCRETE)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

        menu = Gio.Menu()
        menu.append("Choose files…", "app.choose")
        menu.append("Clear selection", "app.clear")
        menu.append("Settings…", "app.settings")
        glass = Gio.Menu()
        for level, label in (("clear", "Clear glass"), ("regular", "Regular glass"), ("tinted", "Tinted glass")):
            glass.append(label, f"app.glass::{level}")
        menu.append_section(None, glass)
        jobs = Gio.Menu()
        jobs.append("Cancel running jobs", "app.cancel")
        menu.append_section(None, jobs)
        end = Gio.Menu()
        end.append("Quit", "app.quit")
        menu.append_section(None, end)
        self.menu = Gtk.PopoverMenu.new_from_model(menu)
        self.menu.set_parent(self)
        self.menu.set_has_arrow(False)

        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self.queue_draw())
        self.refresh()

    # state

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self.hover = None
            self.refresh()

    def set_files(self, paths):
        self.files = [p for p in paths if p]
        self.refresh(pick_mode=True)
        self._animate(1.0 if self.files else 0.88)

    def refresh(self, pick_mode=False):
        sample = self.drag_sample or (self.files[0] if self.files else None)
        self.kind = kind_of(sample) if sample else VIDEO
        self.ext = file_ext(sample) if sample else ""
        self.items = wheel_items(self.mode, self.kind, self.ext)
        # only jump to another wheel when a file is loaded, never mid-drag, so a wheel picked with a key stays put
        if pick_mode and sample and not self.items:
            for mode in MODES:
                if wheel_items(mode, self.kind, self.ext):
                    self.win.set_mode(mode)
                    return
        self.queue_draw()

    def set_jobs(self, busy, progress):
        self.busy = busy
        self.progress = progress
        self.queue_draw()

    def show_flash(self, title, sub=""):
        self.flash = (title, sub)
        if self._flash_timer:
            GLib.source_remove(self._flash_timer)
        self._flash_timer = GLib.timeout_add(2200, self._clear_flash)
        self.queue_draw()

    def _clear_flash(self):
        self.flash = None
        self._flash_timer = 0
        self.queue_draw()
        return GLib.SOURCE_REMOVE

    def hit(self, x, y):
        cx, cy, r0, R = wheel_geometry(self.get_width(), self.get_height(), self.open_t)
        d = math.hypot(x - cx, y - cy)
        if d < r0:
            return -1
        if d > R * HOT_SCALE + 4 or not self.items:
            return None
        step = 2 * math.pi / len(self.items)
        ang = math.atan2(y - cy, x - cx) - self.spin
        return int(((ang + math.pi / 2 + step / 2) % (2 * math.pi)) / step) % len(self.items)

    def _set_hover(self, idx):
        if idx != self.hover:
            self.hover = idx
            self.queue_draw()

    def move_hover(self, delta):
        if self.items:
            base = self.hover if self.hover is not None and self.hover >= 0 else (-1 if delta > 0 else 0)
            self._set_hover((base + delta) % len(self.items))

    def update_input_region(self):
        """Clicks and drops outside the round wheel fall through to the desktop."""
        native = self.get_native()
        surface = native.get_surface() if native else None
        if not surface:
            return
        w, h = self.get_width(), self.get_height()
        cx, cy, _, R = wheel_geometry(w, h, 1.0)
        R += 12
        rects = []
        band = 4
        y = int(cy - R)
        while y < cy + R:
            half = math.sqrt(max(0.0, R * R - (y + band / 2 - cy) ** 2))
            rects.append(cairo.RectangleInt(int(cx - half), y, int(2 * half) + 1, band))
            y += band
        surface.set_input_region(cairo.Region(rects))

    # animation

    def _animate(self, target):
        # opening turns the fan in from -40 degrees, as FanDrop does
        spin_from = SPIN_FROM if target > self.open_t else self.spin
        self._anim = (self.open_t, target, spin_from, None)
        if not self._tick:
            self._tick = self.add_tick_callback(self._on_tick)

    def _on_tick(self, _widget, clock):
        start_v, end_v, spin_from, start_t = self._anim
        now = clock.get_frame_time() / 1e6
        if start_t is None:
            start_t = now
            self._anim = (start_v, end_v, spin_from, now)
        t = now - start_t
        eased = spring(t)
        self.open_t = start_v + (end_v - start_v) * eased
        self.spin = spin_from * (1 - eased)
        self.queue_draw()
        if t >= SPRING_SETTLE:
            self.open_t, self.spin = end_v, 0.0
            self._tick = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    def _draw(self, _area, cr, w, h):
        self.scale = self.get_scale_factor()
        draw_wheel(cr, w, h, self, Adw.StyleManager.get_default().get_dark())

    # pointer

    def _on_pointer_motion(self, _ctrl, x, y):
        self._set_hover(self.hit(x, y))

    def _on_click(self, _gesture, _n, x, y):
        if self._moved:
            return
        self.grab_focus()
        idx = self.hit(x, y)
        if idx == -1:
            self.win.choose_files()
        elif idx is not None and idx < len(self.items):
            if self.files:
                self.win.apply(self.items[idx], self.files)
            else:
                self.win.choose_files(then=self.items[idx])

    def _on_move_begin(self, _gesture, x, y):
        self._moved = False
        self._move_from = (x, y) if self.hit(x, y) == -1 else None

    def _on_move_update(self, gesture, dx, dy):
        if self._move_from and not self._moved and math.hypot(dx, dy) > 6:
            self._moved = True
            x, y = self.translate_coordinates(self.get_native(), *self._move_from)
            self.get_native().get_surface().begin_move(
                gesture.get_device(), gesture.get_current_button(), x, y, gesture.get_current_event_time())

    def _on_menu_click(self, _gesture, _n, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self.menu.set_pointing_to(rect)
        self.menu.popup()

    def _on_scroll(self, _ctrl, _dx, dy):
        step = 1 if dy > 0 else -1
        self.win.set_mode(MODES[(MODES.index(self.mode) + step) % len(MODES)])
        return True

    # drag & drop

    def _on_drag_motion(self, target, x, y):
        if not self.drag_active:
            self.drag_active = True
            self._animate(1.0)
        value = target.get_value()
        if value is not None:
            files = [f.get_path() for f in value.get_files() if f.get_path()]
            if files and files[0] != self.drag_sample:
                self.drag_sample = files[0]
                self.refresh()
        self._start_key_poll()
        self._track_drag_keys(target)
        self._set_hover(self.hit(x, y))
        # LINK as the no-modifier choice keeps it distinct from the Shift/Ctrl/Alt actions
        return Gdk.DragAction.LINK

    def _reset_drag_keys(self):
        self._drag_source_actions = 0
        self._drag_base = None
        self._drag_last = None
        self._polled_mode = None
        if self._key_poll:
            GLib.source_remove(self._key_poll)
            self._key_poll = 0

    def _start_key_poll(self):
        """Ask the Narenj Shell extension for the held modifiers while a file hovers the wheel.

        This sees Ctrl and Alt too, unlike the drag action, which only some drag sources
        let through, and keeps working while the pointer stands still.
        """
        if self._shell_keys and not self._key_poll:
            self._key_poll = GLib.timeout_add(70, self._poll_keys)

    def _poll_keys(self):
        if IS_WINDOWS:
            self._apply_modifiers(win32_modifiers())
            return GLib.SOURCE_CONTINUE
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call(
            "org.gnome.Shell", "/ir/narenj/Shell", "ir.narenj.Shell", "GetModifiers", None,
            GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, 200, None, self._on_keys)
        return GLib.SOURCE_CONTINUE

    def _on_keys(self, bus, result):
        try:
            mods = bus.call_finish(result).unpack()[0]
        except GLib.Error as e:
            if DEBUG:
                print("shell modifiers unavailable:", e.message, flush=True)
            self._shell_keys = False  # extension not loaded yet; drag actions still cover Shift
            self._reset_drag_keys()
            return
        self._apply_modifiers(mods)

    def _apply_modifiers(self, mods):
        if not self.drag_active:
            return
        mode = (CONVERT if mods & Gdk.ModifierType.SHIFT_MASK else
                TOOLS if mods & Gdk.ModifierType.CONTROL_MASK else
                ACTIONS if mods & Gdk.ModifierType.ALT_MASK else None)
        if DEBUG:
            print("shell modifiers:", mods, mode, flush=True)
        # react to presses only, so letting go of the key keeps the chosen wheel
        if mode and mode != self._polled_mode:
            self.win.set_mode(mode)
        self._polled_mode = mode

    def _track_drag_keys(self, target):
        """Switch wheels from Shift/Ctrl/Alt held during a drag.

        On Wayland the keyboard stays with the app the file is dragged from, so key events
        never arrive here. Mutter instead turns held modifiers into the drag action it
        reports: Shift = move, Ctrl = copy, Alt = ask.
        """
        drop = target.get_current_drop()
        actions = int(drop.get_actions()) if drop else 0
        if DEBUG:
            print("drag actions:", Gdk.DragAction(actions), flush=True)
        if actions & (actions - 1):
            # several bits: still the source's offer, nothing chosen yet
            self._drag_source_actions = actions
            return
        if self._drag_base is None:
            self._drag_base = LINK if self._drag_source_actions & LINK else actions
        if actions != self._drag_last and actions != self._drag_base and actions in ACTION_MODE:
            self.win.set_mode(ACTION_MODE[actions])
        self._drag_last = actions

    def _on_drag_leave(self, _target):
        self.drag_active = False
        self._reset_drag_keys()
        self.drag_sample = None
        self.hover = None
        self.refresh()
        self._animate(1.0 if self.files else 0.88)

    def _on_drop(self, _target, value, x, y):
        self.drag_active = False
        self._reset_drag_keys()
        self.drag_sample = None
        files = [f.get_path() for f in value.get_files() if f.get_path()]
        if not files:
            self.win.toast("Only local files")
            return False
        idx = self.hit(x, y)
        self.set_files(files)
        if idx is not None and 0 <= idx < len(self.items):
            self.win.apply(self.items[idx], files)
        self.hover = idx
        return True


# ---------------------------------------------------------------- jobs

class Job:
    def __init__(self, win, src, dst, action):
        self.win = win
        self.src = src
        self.dst = dst
        self.action = action
        self.fraction = 0.0
        self.proc = None
        self.cancelled = False

    def progress(self, fraction, _elapsed, _total):
        self.fraction = min(1.0, fraction)
        self.win.jobs_changed()

    def finish(self, ok, message):
        self.proc = None
        self.win.job_finished(self, ok, message)


def run_job(job, cmd, duration):
    with tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True, **NO_CONSOLE)
        except OSError as e:
            GLib.idle_add(job.finish, False, str(e))
            return
        job.proc = proc
        for line in proc.stdout:
            key, _, val = line.strip().partition("=")
            if key in ("out_time_us", "out_time_ms") and duration > 0:
                try:
                    t = int(val) / 1e6
                except ValueError:
                    continue
                GLib.idle_add(job.progress, max(0.0, t / duration), max(0.0, t), duration)
        code = proc.wait()
        err.seek(0)
        tail = [l for l in err.read().decode(errors="replace").splitlines() if l.strip()]
    if code == 0:
        size = human_size(os.path.getsize(job.dst)) if os.path.exists(job.dst) else ""
        GLib.idle_add(job.finish, True, size)
    else:
        if os.path.exists(job.dst):
            os.remove(job.dst)
        msg = "Cancelled" if job.cancelled else (tail[-1] if tail else f"ffmpeg exited with {code}")
        GLib.idle_add(job.finish, False, msg)


# ---------------------------------------------------------------- window

CSS = """
window.narenj-float, window.narenj-float.background {
  background: none; box-shadow: none; border-radius: 0;
}
"""


class Window(Gtk.ApplicationWindow):
    """A borderless, transparent window that is nothing but the wheel."""

    def __init__(self, app):
        super().__init__(application=app, title="Narenj")
        self.set_decorated(False)
        self.set_resizable(False)
        self.add_css_class("narenj-float")
        self.jobs = []
        self.last_output = None

        self.wheel = Wheel(self)
        self.set_child(self.wheel)
        self.connect("map", lambda *_: GLib.idle_add(self.wheel.update_input_region))
        if IS_WINDOWS:
            self.connect("map", lambda *_: GLib.idle_add(win32_keep_on_top, self))

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        if not FFMPEG:
            GLib.idle_add(self.toast, "ffmpeg not found", "sudo apt install ffmpeg")

    # modes & keys

    def set_mode(self, mode):
        self.wheel.set_mode(mode)

    def _on_key(self, _ctrl, keyval, _code, state):
        modifier_mode = {
            Gdk.KEY_Shift_L: CONVERT, Gdk.KEY_Shift_R: CONVERT,
            Gdk.KEY_Control_L: TOOLS, Gdk.KEY_Control_R: TOOLS,
            Gdk.KEY_Alt_L: ACTIONS, Gdk.KEY_Alt_R: ACTIONS,
        }.get(keyval)
        if modifier_mode:
            self.set_mode(modifier_mode)
            return False
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if keyval == Gdk.KEY_o and ctrl:
            self.choose_files()
        elif keyval == Gdk.KEY_q and ctrl:
            self.get_application().quit()
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_Down):
            self.wheel.move_hover(1)
        elif keyval in (Gdk.KEY_Left, Gdk.KEY_Up):
            self.wheel.move_hover(-1)
        elif keyval == Gdk.KEY_Tab:
            self.set_mode(MODES[(MODES.index(self.wheel.mode) + 1) % len(MODES)])
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            h = self.wheel.hover
            if h is not None and 0 <= h < len(self.wheel.items):
                if self.wheel.files:
                    self.apply(self.wheel.items[h], self.wheel.files)
                else:
                    self.choose_files(then=self.wheel.items[h])
            elif not self.wheel.files:
                self.choose_files()
        elif keyval == Gdk.KEY_Escape:
            self.wheel.set_files([])
        else:
            return False
        return True

    # file choosing

    def choose_files(self, then=None):
        chooser = Gtk.FileChooserNative.new("Choose files", self, Gtk.FileChooserAction.OPEN, "_Open", "_Cancel")
        chooser.set_select_multiple(True)

        def on_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                model = dialog.get_files()
                paths = [model.get_item(i).get_path() for i in range(model.get_n_items())]
                self.wheel.set_files(paths)
                if then and self.wheel.files and then.accepts(self.wheel.kind):
                    self.apply(then, self.wheel.files)
            self._chooser = None

        chooser.connect("response", on_response)
        self._chooser = chooser
        chooser.show()

    def open_paths(self, paths):
        self.wheel.set_files(paths)

    # applying actions

    def apply(self, action, files):
        if action.handler:
            getattr(self, f"do_{action.handler}")(files)
            return
        if not FFMPEG:
            self.toast("ffmpeg not found", "sudo apt install ffmpeg")
            return
        targets = [(f, kind_of(f)) for f in files if action.accepts(kind_of(f))]
        if not targets:
            self.toast("Not for this file", action.label)
            return
        if action.id == "srt":
            targets = [(f, k) for f, k in targets if has_stream(f, "subtitle")]
            if not targets:
                self.toast("No subtitles", "in this file")
                return
        if action.prompt == "trim":
            self.ask_trim(targets, action)
            return
        for src, kind in targets:
            self.start_job(src, kind, action)

    def start_job(self, src, kind, action, extra_in=(), extra_out=(), duration=None):
        dst = output_path(src, action, kind)
        cmd = ffmpeg_command(src, kind, action, dst, extra_in, extra_out)
        self.run_ffmpeg(src, dst, action, lambda: (
            cmd, duration if duration is not None else (probe_duration(src) if kind != IMAGE else 0)))

    def run_ffmpeg(self, src, dst, action, prepare):
        """Track one ffmpeg run as a job. `prepare` runs off the UI thread (it may probe files)
        and returns the command and its length in seconds."""
        job = Job(self, src, dst, action)
        self.jobs.append(job)
        self.jobs_changed()

        def worker():
            try:
                cmd, total = prepare()
            except (StopIteration, KeyError, OSError) as e:
                GLib.idle_add(job.finish, False, f"Could not read the files ({e.__class__.__name__})")
                return
            run_job(job, cmd, total)

        threading.Thread(target=worker, daemon=True).start()

    def jobs_changed(self):
        busy = len(self.jobs)
        progress = sum(j.fraction for j in self.jobs) / busy if busy else 0.0
        self.wheel.set_jobs(busy, progress)

    def job_finished(self, job, ok, message):
        if job in self.jobs:
            self.jobs.remove(job)
        self.jobs_changed()
        name = os.path.basename(job.dst)
        if ok:
            self.last_output = job.dst
            self.wheel.show_flash("Done ✓", name)
            self.notify(f"Saved {name}", f"{job.action.label} · {message}", reveal=job.dst)
        elif job.cancelled:
            self.wheel.show_flash("Cancelled", name)
        else:
            self.wheel.show_flash("Failed", job.action.label)
            self.notify(f"{job.action.label} failed", message)
        if not self.jobs and not self.get_visible():
            # closed with the shortcut while ffmpeg was still busy
            self.get_application().quit()

    def cancel_jobs(self):
        for job in list(self.jobs):
            if job.proc:
                job.cancelled = True
                job.proc.terminate()

    def notify(self, title, body, reveal=None):
        note = Gio.Notification.new(title)
        note.set_body(body)
        if reveal:
            target = GLib.Variant.new_string(reveal)
            note.add_button_with_target("Show in Files", "app.reveal", target)
            note.set_default_action_and_target("app.reveal", target)
        self.get_application().send_notification(None, note)

    def toast(self, title, sub=""):
        self.wheel.show_flash(title, sub)
        return False

    def ask_trim(self, targets, action):
        src, _ = targets[0]
        total = probe_duration(src)
        dialog = Gtk.Window(transient_for=self, modal=True, title="Trim", resizable=False)
        dialog.set_default_size(340, -1)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{side}")(18)
        header = Gtk.Label(label=f"Trim {os.path.basename(src)}", xalign=0,
                           ellipsize=Pango.EllipsizeMode.MIDDLE)
        header.add_css_class("title-4")
        box.append(header)
        info = Gtk.Label(label=f"Length {format_time(total)}  ·  use m:ss or seconds", xalign=0)
        info.add_css_class("dim-label")
        box.append(info)
        grid = Gtk.Grid(column_spacing=10, row_spacing=8)
        start = Gtk.Entry(text="0:00", hexpand=True)
        end = Gtk.Entry(text=format_time(total) if total else "", hexpand=True)
        grid.attach(Gtk.Label(label="Start", xalign=0), 0, 0, 1, 1)
        grid.attach(start, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label="End", xalign=0), 0, 1, 1, 1)
        grid.attach(end, 1, 1, 1, 1)
        box.append(grid)
        buttons = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        ok = Gtk.Button(label="Trim")
        ok.add_css_class("suggested-action")
        buttons.append(cancel)
        buttons.append(ok)
        box.append(buttons)
        dialog.set_child(box)

        def do_trim(*_):
            try:
                s = parse_time(start.get_text())
                e = parse_time(end.get_text()) if end.get_text().strip() else total
            except ValueError:
                info.set_text("Use times like 1:30 or 90")
                return
            if e <= s:
                info.set_text("End must be after start")
                return
            dialog.close()
            for path, kind in targets:
                self.start_job(path, kind, action, extra_in=("-ss", str(s)),
                               extra_out=("-t", str(e - s)), duration=e - s)

        cancel.connect("clicked", lambda *_: dialog.close())
        ok.connect("clicked", do_trim)
        end.connect("activate", do_trim)
        dialog.present()

    # file actions

    def do_open(self, files):
        for f in files:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(f).get_uri(), None)

    def do_reveal(self, files):
        for f in files:
            self.reveal(f)

    def reveal(self, path):
        if IS_WINDOWS:
            subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            return
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call_sync("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                          "org.freedesktop.FileManager1", "ShowItems",
                          GLib.Variant("(ass)", ([Gio.File.new_for_path(path).get_uri()], "")),
                          None, Gio.DBusCallFlags.NONE, 3000, None)
        except GLib.Error:
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(folder).get_uri(), None)

    def do_copy(self, files):
        text = "\n".join(files)
        provider = Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", GLib.Bytes.new(text.encode()))
        self.get_clipboard().set_content(provider)
        self.toast("Copied ✓", "path" + ("s" if len(files) > 1 else ""))

    def do_join(self, files):
        join = next(a for a in WHEELS[ACTIONS] if a.id == "join")
        kind = kind_of(files[0])
        parts = sorted((f for f in files if kind_of(f) == kind), key=natural_key)
        if kind not in join.spec or len(parts) < 2:
            self.toast("Join", "drop 2 or more videos or songs")
            return
        dst = output_path(parts[0], join, kind)
        self.run_ffmpeg(parts[0], dst, join, lambda: (
            join_command(parts, kind, dst), sum(probe_duration(f) for f in parts)))

    def do_trash(self, files):
        trashed = 0
        for f in files:
            try:
                Gio.File.new_for_path(f).trash(None)
                trashed += 1
            except GLib.Error as e:
                self.notify("Could not trash", e.message)
        if trashed:
            self.wheel.set_files([f for f in self.wheel.files if os.path.exists(f)])
            self.toast("Trashed ✓", f"{trashed} item{'s' if trashed > 1 else ''}")

    def do_info(self, files):
        path = files[0]
        data = probe(path)
        fmt = data.get("format", {})
        lines = []
        if fmt.get("format_long_name"):
            lines.append(fmt["format_long_name"])
        if fmt.get("duration"):
            lines.append(f"Duration  {format_time(float(fmt['duration']))}")
        if fmt.get("size"):
            lines.append(f"Size  {human_size(fmt['size'])}")
        if fmt.get("bit_rate"):
            lines.append(f"Bitrate  {int(fmt['bit_rate']) // 1000} kb/s")
        for st in data.get("streams", []):
            kind = st.get("codec_type", "?")
            desc = st.get("codec_name", "?")
            if kind == "video":
                desc += f"  {st.get('width')}×{st.get('height')}"
                rate = st.get("r_frame_rate", "0/1").split("/")
                if len(rate) == 2 and float(rate[1] or 1):
                    desc += f"  {float(rate[0]) / float(rate[1]):.3g} fps"
            elif kind == "audio":
                desc += f"  {st.get('sample_rate')} Hz  {st.get('channels')} ch"
            lines.append(f"{kind.capitalize()}  {desc}")
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, buttons=Gtk.ButtonsType.CLOSE,
                                   text=os.path.basename(path))
        dialog.set_property("secondary-text", "\n".join(lines) or "ffprobe could not read this file")
        dialog.connect("response", lambda d, _r: d.destroy())
        dialog.present()


class ShortcutRow(Adw.ActionRow):
    """The toggle shortcut: click it, then press a new key combination."""

    MODIFIER_KEYS = {Gdk.KEY_Shift_L, Gdk.KEY_Shift_R, Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Alt_L,
                     Gdk.KEY_Alt_R, Gdk.KEY_Super_L, Gdk.KEY_Super_R, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R,
                     Gdk.KEY_ISO_Level3_Shift}

    def __init__(self, window):
        super().__init__(title="Open and close the wheel",
                         subtitle="Click, then press new keys. Esc cancels, Backspace turns it off.")
        self.binding = shortcut_settings()
        self.previous = None  # the old shortcut while we listen for a new one
        self.keys = Gtk.ShortcutLabel(disabled_text="Off")
        self.button = Gtk.Button(child=self.keys, valign=Gtk.Align.CENTER)
        self.button.connect("clicked", self._listen)
        self.add_suffix(self.button)
        self.set_activatable_widget(self.button)
        if self.binding:
            self.keys.set_accelerator(self.binding.get_string("binding"))
        else:
            self.set_subtitle("On Windows: Start menu › Narenj › Properties › Shortcut key"
                              if IS_WINDOWS else "Needs GNOME")
            self.set_sensitive(False)
        listen = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        listen.connect("key-pressed", self._on_key)
        window.add_controller(listen)
        window.connect("close-request", lambda *_: self.previous is not None and self._finish(self.previous))

    def _listen(self, _button):
        if self.previous is not None:
            return
        self.previous = self.binding.get_string("binding")
        # switch the old shortcut off meanwhile, or pressing it would close Narenj
        self.binding.set_string("binding", "")
        self.button.set_child(Gtk.Label(label="Press keys…"))

    def _on_key(self, _ctrl, keyval, _code, state):
        if self.previous is None:
            return False
        mods = state & Gtk.accelerator_get_default_mod_mask()
        if keyval == Gdk.KEY_Escape and not mods:
            self._finish(self.previous)
        elif keyval == Gdk.KEY_BackSpace and not mods:
            self._finish("")
        elif keyval not in self.MODIFIER_KEYS and mods & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK
                                                          | Gdk.ModifierType.SUPER_MASK):
            self._finish(Gtk.accelerator_name(Gdk.keyval_to_lower(keyval), mods))
        return True  # plain keys need a Ctrl, Alt or Super with them; keep listening

    def _finish(self, accelerator):
        self.binding.set_string("binding", accelerator)
        Gio.Settings.sync()
        self.previous = None
        self.keys.set_accelerator(accelerator)
        self.button.set_child(self.keys)
        return False


class SettingsWindow(Adw.PreferencesWindow):
    GLASS = ("clear", "regular", "tinted")

    def __init__(self, app):
        super().__init__(application=app, title="Narenj Settings", search_enabled=False)
        self.set_default_size(480, 400)
        self.app = app
        page = Adw.PreferencesPage()

        wheel = Adw.PreferencesGroup(title="Wheel")
        mode = Adw.ComboRow(title="Opens on", subtitle="Shift, Ctrl and Alt still switch wheels",
                            model=Gtk.StringList.new([MODE_TITLES[m] for m in MODES]))
        mode.set_selected(MODES.index(default_mode()))
        mode.connect("notify::selected", self._on_mode)
        wheel.add(mode)
        glass = Adw.ComboRow(title="Glass", subtitle="How much of the desktop shows through",
                             model=Gtk.StringList.new(["Clear", "Regular", "Tinted"]))
        current = app.lookup_action("glass").get_state().get_string()
        glass.set_selected(self.GLASS.index(current) if current in self.GLASS else 1)
        glass.connect("notify::selected", self._on_glass)
        wheel.add(glass)
        page.add(wheel)

        keys = Adw.PreferencesGroup(title="Keyboard")
        keys.add(ShortcutRow(self))
        page.add(keys)
        self.add(page)

    def _on_mode(self, row, _pspec):
        save_settings({**load_settings(), "default_mode": MODES[row.get_selected()]})

    def _on_glass(self, row, _pspec):
        self.app.activate_action("glass", GLib.Variant.new_string(self.GLASS[row.get_selected()]))


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.win = None
        self.settings_win = None
        self.add_main_option("toggle", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Open the wheel, or close it if it is already open", None)
        self.add_main_option("setup", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Add the Ctrl+Alt+N shortcut and enable the always-on-top extension", None)
        reveal = Gio.SimpleAction.new("reveal", GLib.VariantType.new("s"))
        reveal.connect("activate", lambda _a, p: self.win and self.win.reveal(p.get_string()))
        self.add_action(reveal)
        for name, callback in (
            ("choose", lambda: self.win.choose_files()),
            ("clear", lambda: self.win.wheel.set_files([])),
            ("cancel", lambda: self.win.cancel_jobs()),
            ("quit", self.quit),
            ("toggle", self.toggle),
            ("settings", self.show_settings),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            self.add_action(action)
        glass = Gio.SimpleAction.new_stateful("glass", GLib.VariantType.new("s"),
                                              GLib.Variant.new_string(load_settings().get("glass", "regular")))
        glass.connect("activate", self._on_glass)
        self.add_action(glass)

    def _on_glass(self, action, value):
        action.set_state(value)
        level = value.get_string()
        save_settings({**load_settings(), "glass": level})
        if self.win:
            self.win.wheel.glass = level
            self.win.wheel.queue_draw()

    def show_settings(self):
        if not self.settings_win:
            self.settings_win = SettingsWindow(self)
            self.settings_win.connect("destroy", lambda *_: setattr(self, "settings_win", None))
        self.settings_win.present()

    def do_handle_local_options(self, options):
        if options.contains("setup"):
            changed = desktop_setup(force=True)
            save_settings({**load_settings(), "setup_done": True})
            print("Narenj: " + (", ".join(changed) + " set up." if changed else "nothing to change."))
            if "extension" in changed:
                print("Log out and back in once so GNOME Shell loads the always-on-top extension.")
            return 0
        if options.contains("toggle"):
            self.register(None)
            if self.get_is_remote():
                self.activate_action("toggle", None)
                return 0
        return -1

    def toggle(self):
        if not self.win or not self.win.get_visible():
            self.do_activate()
        elif self.win.jobs:
            # keep ffmpeg running in the background; the next toggle brings the wheel back
            self.win.set_visible(False)
        else:
            self.quit()

    def do_startup(self):
        Adw.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(APP_ID)
        css = Gtk.CssProvider()
        css.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.settings", ["<Control>comma"])

    def do_activate(self):
        if not self.win:
            self.win = Window(self)
            self.first_run()
            if os.environ.get("NARENJ_SELF_TEST"):
                self.self_test()
        self.win.present()

    def self_test(self):
        """NARENJ_SELF_TEST=1: show the wheel and the settings, then quit; CI uses it to check
        that a build starts. Errors are counted by the excepthook in __main__."""
        def settings():
            self.show_settings()
            GLib.timeout_add(1500, done)
            return False

        def done():
            print("self-test: wheel and settings shown", flush=True)
            self.quit()
            return False

        GLib.timeout_add(1500, settings)

    def first_run(self):
        settings = load_settings()
        if settings.get("setup_done"):
            return
        changed = desktop_setup()
        save_settings({**settings, "setup_done": True})
        if changed:
            self.win.notify("Narenj is set up", "Ctrl+Alt+N opens and closes the wheel. Log out and back in once "
                            "to keep it above other windows.")

    def do_open(self, files, _n, _hint):
        self.do_activate()
        self.win.open_paths([f.get_path() for f in files if f.get_path()])


if __name__ == "__main__":
    errors = []
    if os.environ.get("NARENJ_SELF_TEST"):
        def count_errors(*exc, _hook=sys.excepthook):
            errors.append(exc)
            _hook(*exc)
        sys.excepthook = count_errors
    status = App().run(sys.argv)
    sys.exit(status or (1 if errors else 0))
