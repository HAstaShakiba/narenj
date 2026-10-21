#!/usr/bin/env python3
"""Draws the wheel pictures for the website with Narenj's own drawing code, on a transparent
background, in the light and dark theme:  python3 packaging/site/render-wheels.py <out-dir>"""
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
import narenj as n  # noqa: E402

OUT = sys.argv[1]
SCALE = 2
WHEELS = {  # mode: (sample file, highlighted wedge)
    n.CONVERT: ("holiday.mp4", 4),
    n.TOOLS: ("holiday.mp4", 1),
    n.ACTIONS: ("holiday.mp4", 2),
}

for mode, (sample, hover) in WHEELS.items():
    kind, ext = n.kind_of(sample), n.file_ext(sample)
    for theme in ("light", "dark"):
        s = types.SimpleNamespace(mode=mode, items=n.wheel_items(mode, kind, ext), hover=hover,
                                  files=[f"/x/{sample}"], open_t=1, drag_active=False, kind=kind, busy=0,
                                  progress=0, flash=None, scale=SCALE, glass="tinted", bar_hover=None)
        w, h = 440, 440 + n.WHEEL_TOP
        surface = n.cairo.ImageSurface(n.cairo.FORMAT_ARGB32, w * SCALE, h * SCALE)
        surface.set_device_scale(SCALE, SCALE)
        n.draw_wheel(n.cairo.Context(surface), w, h, s, theme == "dark")
        surface.write_to_png(os.path.join(OUT, f"wheel-{mode}-{theme}.png"))
