#!/usr/bin/env python3
"""Generate src/mac/assets/grid_icon.png — a 4×4 grid template icon for the menu bar."""
import os
import sys

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from AppKit import (
    NSBitmapImageRep,
    NSBezierPath,
    NSColor,
    NSGraphicsContext,
    NSImage,
    NSPNGFileType,
)

GRID = 4
SIZE = 44          # logical points (menu bar icons are ~22pt; 2× for Retina)
CELL = SIZE / GRID
DOT = CELL * 0.56  # fill ratio within each cell
RADIUS = DOT * 0.3 # corner radius
MARGIN = (CELL - DOT) / 2

OUT = os.path.join(os.path.dirname(__file__), '..', 'src', 'mac', 'assets', 'grid_icon.png')


def make_icon(path: str) -> None:
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, SIZE, SIZE, 8, 4, True, False,
        'NSCalibratedRGBColorSpace', 0, 0,
    )
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(ctx)

    # Transparent background
    NSColor.clearColor().set()
    NSBezierPath.fillRect_(((0, 0), (SIZE, SIZE)))

    # Black dots
    NSColor.blackColor().set()
    for row in range(GRID):
        for col in range(GRID):
            x = col * CELL + MARGIN
            y = row * CELL + MARGIN
            dot_path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                ((x, y), (DOT, DOT)), RADIUS, RADIUS,
            )
            dot_path.fill()

    NSGraphicsContext.restoreGraphicsState()

    img = NSImage.alloc().initWithSize_((SIZE / 2, SIZE / 2))
    img.addRepresentation_(rep)
    img.setTemplate_(True)

    tiff = img.TIFFRepresentation()
    bitmap = NSBitmapImageRep.imageRepWithData_(tiff)
    png = bitmap.representationUsingType_properties_(NSPNGFileType, None)

    out = os.path.abspath(path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(bytes(png))
    print(f"Written: {out}")


if __name__ == '__main__':
    make_icon(OUT)
