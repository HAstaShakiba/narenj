#!/usr/bin/env python3
"""Draws the website's pictures with Narenj's own drawing code:
    python3 packaging/site/render-wheels.py <site-dir>
writes screenshots/wheel-<mode>-<theme>.png (transparent, light and dark), social-card.png
(the 1200x630 link preview) and social-icon.png (180x180, for home screens)."""
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
import narenj as n  # noqa: E402

cairo, Pango, PangoCairo, Rsvg = n.cairo, n.Pango, n.PangoCairo, n.Rsvg
SITE = sys.argv[1]
SCALE = 2
WHEEL_W, WHEEL_H = 440, 440 + n.WHEEL_TOP
WHEELS = {  # mode: (sample file, highlighted wedge)
    n.CONVERT: ("holiday.mp4", 4),
    n.TOOLS: ("holiday.mp4", 1),
    n.ACTIONS: ("holiday.mp4", 2),
}


def wheel_surface(mode, dark, scale=SCALE):
    sample, hover = WHEELS[mode]
    kind, ext = n.kind_of(sample), n.file_ext(sample)
    s = types.SimpleNamespace(mode=mode, items=n.wheel_items(mode, kind, ext), hover=hover,
                              files=[f"/x/{sample}"], open_t=1, drag_active=False, kind=kind, busy=0,
                              progress=0, flash=None, scale=scale, glass="tinted", bar_hover=None)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WHEEL_W * scale, WHEEL_H * scale)
    surface.set_device_scale(scale, scale)
    n.draw_wheel(cairo.Context(surface), WHEEL_W, WHEEL_H, s, dark)
    return surface


os.makedirs(os.path.join(SITE, "screenshots"), exist_ok=True)
for mode in WHEELS:
    for theme in ("light", "dark"):
        wheel_surface(mode, theme == "dark").write_to_png(
            os.path.join(SITE, "screenshots", f"wheel-{mode}-{theme}.png"))

# the link preview: wordmark and promise on the left, the Tools wheel on the right
W, H = 1200, 630
card = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
cr = cairo.Context(card)
background = cairo.LinearGradient(0, 0, W, H)
background.add_color_stop_rgb(0, 0.17, 0.10, 0.07)
background.add_color_stop_rgb(1, 0.08, 0.07, 0.06)
cr.set_source(background)
cr.paint()
glow = cairo.RadialGradient(900, 330, 40, 900, 330, 380)
glow.add_color_stop_rgba(0, 1.0, 0.42, 0.12, 0.45)
glow.add_color_stop_rgba(1, 1.0, 0.42, 0.12, 0)
cr.set_source(glow)
cr.paint()
cr.save()
zoom = 0.92
cr.translate(900 - WHEEL_W * zoom / 2, 315 - WHEEL_H * zoom / 2)
cr.scale(zoom, zoom)
cr.set_source_surface(wheel_surface(n.TOOLS, True, scale=1), 0, 0)
cr.paint()
cr.restore()


def text(markup, size, color, x, y, width, weight="Bold"):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription.from_string(f"Sans {weight} {size}"))
    layout.set_width(int(width * Pango.SCALE))
    layout.set_wrap(Pango.WrapMode.WORD)
    layout.set_markup(markup, -1)
    cr.set_source_rgb(*color)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return layout.get_pixel_extents()[1].height


logo = Rsvg.Handle.new_from_file(os.path.join(ROOT, "narenj.svg"))
viewport = Rsvg.Rectangle()
viewport.x, viewport.y, viewport.width, viewport.height = 70, 70, 84, 84
logo.render_document(cr, viewport)
y = 70 + text("Narenj", 46, (1, 1, 1), 172, 78, 400)
y = 200
y += text("The free Tangerine alternative for Windows and Linux", 31, (1, 1, 1), 70, y, 560) + 22
y += text("Drag a file onto the wheel to convert, compress or trim it: video, audio, images, "
          "PDFs, documents and archives.", 17, (0.85, 0.80, 0.76), 70, y, 540, "Regular") + 30
text('<span foreground="#ff8a4d">Free · open source · offline</span>  ·  Windows · Linux · macOS', 15,
     (0.85, 0.80, 0.76), 70, y, 660)
card.write_to_png(os.path.join(SITE, "social-card.png"))

# home-screen icon
icon = cairo.ImageSurface(cairo.FORMAT_ARGB32, 180, 180)
viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 180, 180
logo.render_document(cairo.Context(icon), viewport)
icon.write_to_png(os.path.join(SITE, "social-icon.png"))
