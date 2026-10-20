# PyInstaller spec for the macOS app. Run on a Mac with Homebrew's GTK stack (see the macos job
# in .github/workflows/ci.yml):
#   NARENJ_FFMPEG_DIR=<dir> NARENJ_ICNS=<icns> NARENJ_VERSION=<version> pyinstaller packaging/macos/narenj.spec
# NARENJ_FFMPEG_DIR holds ffmpeg, ffprobe and their dylibs from packaging/build-ffmpeg.sh.
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
FFMPEG = os.environ["NARENJ_FFMPEG_DIR"]
ffmpeg_files = [os.path.join(FFMPEG, f) for f in sorted(os.listdir(FFMPEG))
                if (f in ("ffmpeg", "ffprobe") or f.endswith(".dylib")) and not os.path.islink(os.path.join(FFMPEG, f))]

a = Analysis(
    [os.path.join(ROOT, "narenj.py")],
    binaries=[(f, "ffmpeg") for f in ffmpeg_files],
    datas=[(os.path.join(ROOT, "icons", f), "icons") for f in os.listdir(os.path.join(ROOT, "icons"))
           if f.endswith(".svg")],
    hiddenimports=["gi.repository.Adw", "gi.repository.Rsvg", "gi.repository.PangoCairo"],
    hooksconfig={
        "gi": {
            "module-versions": {"Gtk": "4.0", "Gdk": "4.0", "Gsk": "4.0", "Adw": "1", "Rsvg": "2.0"},
            "icons": ["Adwaita", "hicolor"],
            "themes": [],
            "languages": [],
        },
    },
    excludes=["tkinter", "unittest", "pydoc"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Narenj", console=False, strip=True)
coll = COLLECT(exe, a.binaries, a.datas, name="Narenj", strip=True)
app = BUNDLE(
    coll,
    name="Narenj.app",
    icon=os.environ.get("NARENJ_ICNS"),
    bundle_identifier="ir.narenj.Narenj",
    version=os.environ.get("NARENJ_VERSION", "0.0.0"),
    info_plist={
        "CFBundleDisplayName": "Narenj",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "13.0",
    },
)
