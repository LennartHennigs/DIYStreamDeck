#!/usr/bin/env python3
"""Generate src/mac/assets/app_icon.icns — the Dock/Finder icon for the .app.

A colored cousin of the monochrome menu-bar icon (scripts/generate_icon.py):
a rounded-square background panel with a 4×4 grid of grey, slightly-rounded
keys. The bottom-right key is a darker grey for a bit of visual interest.

Renders each required iconset size with AppKit, then folds them into an .icns
with the macOS-builtin `iconutil`.
"""
import os
import subprocess
import sys
import tempfile

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from AppKit import (
    NSBitmapImageRep,
    NSBezierPath,
    NSColor,
    NSGraphicsContext,
    NSPNGFileType,
)

GRID = 4
OUT = os.path.join(os.path.dirname(__file__), '..',
                   'src', 'mac', 'assets', 'app_icon.icns')

# .iconset filename -> pixel size
ICONSET = {
    'icon_16x16.png': 16,
    'icon_16x16@2x.png': 32,
    'icon_32x32.png': 32,
    'icon_32x32@2x.png': 64,
    'icon_128x128.png': 128,
    'icon_128x128@2x.png': 256,
    'icon_256x256.png': 256,
    'icon_256x256@2x.png': 512,
    'icon_512x512.png': 512,
    'icon_512x512@2x.png': 1024,
}


def _rgb(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(
        r / 255.0, g / 255.0, b / 255.0, a)


def _rounded(x, y, w, h, radius):
    return NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((x, y), (w, h)), radius, radius)


def _render_png(size: int) -> bytes:
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False,
        'NSCalibratedRGBColorSpace', 0, 0,
    )
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)

    NSColor.clearColor().set()
    NSBezierPath.fillRect_(((0, 0), (size, size)))

    # Background rounded-square panel (light neutral).
    margin = size * 0.06
    panel = size - 2 * margin
    _rgb(238, 238, 240).set()
    _rounded(margin, margin, panel, panel, size * 0.22).fill()

    # 4×4 grid of keys inside the panel.
    inset = margin + panel * 0.12
    area = panel * 0.76
    cell = area / GRID
    gap = cell * 0.14
    key = cell - gap
    key_radius = key * 0.26  # slightly rounded corners
    key_color = _rgb(154, 154, 160)       # medium grey
    dark_key_color = _rgb(90, 90, 96)     # darker grey (visual bottom-right)
    for row in range(GRID):            # row 0 = visual bottom (AppKit origin)
        for col in range(GRID):        # col 3 = visual right
            x = inset + col * cell + gap / 2
            y = inset + row * cell + gap / 2
            is_bottom_right = row == 0 and col == GRID - 1
            (dark_key_color if is_bottom_right else key_color).set()
            _rounded(x, y, key, key, key_radius).fill()

    NSGraphicsContext.restoreGraphicsState()
    png = rep.representationUsingType_properties_(NSPNGFileType, None)
    return bytes(png)


def make_icns(path: str) -> None:
    out = os.path.abspath(path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, 'app.iconset')
        os.makedirs(iconset)
        for name, size in ICONSET.items():
            with open(os.path.join(iconset, name), 'wb') as f:
                f.write(_render_png(size))
        subprocess.run(['iconutil', '-c', 'icns', iconset, '-o', out],
                       check=True)
    print(f"Written: {out}")


if __name__ == '__main__':
    make_icns(OUT)
