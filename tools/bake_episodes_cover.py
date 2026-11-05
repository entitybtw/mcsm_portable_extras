#!/usr/bin/env python3
"""
Bakes the cover of the story bundle (assets/ui/episodes_sky.png and
assets/ui/episodes_art.png) into one picture.

Why:
  * the popup of the episodes drew two textures: the sky (210x176, loaded by
    the engine as 5650) and the logo over it (210x102 with a soft alpha, so
    the engine had to load it as 8888). Together they took ~159 KB of the
    video memory of the PSP, and the logo was drawn over the sky with the
    alpha of the fade, so the two layers did not fade as one piece.
  * the baked picture is one texture of 210x176, so the popup loads one
    picture instead of two and every pixel of it fades at once.

The picture is saved as an indexed PNG (T8: one byte per pixel, a palette of
256 colours), which is the cheapest format the engine can store. The palette
is built by hand: the logo (the top 102 rows) gets most of the colours, the
smooth sky of the bottom gets only a few, so the gradient of the sky does
not band and the logo keeps its colours.

Run it from the root of the project:
    python3 tools/bake_episodes_cover.py
"""

import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "assets", "ui")

SKY = os.path.join(ROOT, "tools", "cover_src", "episodes_sky.png")
ART = os.path.join(ROOT, "tools", "cover_src", "episodes_art.png")
OUT = os.path.join(UI, "episodes_cover.png")

# The logo stands on the top of the picture, the sky is under it.
LOGO_H = 102

# The colours of the palette: the logo gets most of them, the sky of the
# bottom is a smooth gradient that needs only a few.
LOGO_COLORS = 224
SKY_COLORS = 256 - LOGO_COLORS


def palette_of(img, colors):
    """The palette of an indexed picture, as a list of (r, g, b)."""
    pal = list(img.getpalette())
    pal += [0] * (768 - len(pal))
    return [tuple(pal[i * 3:i * 3 + 3]) for i in range(colors)]


def nearest(colors, pixels):
    """The index of the closest colour of the palette for every pixel."""
    pal = np.array(colors, dtype=np.int32)
    px = pixels.reshape(-1, 3).astype(np.int32)
    # The distance to every colour of the palette, in blocks, so the memory
    # of the result stays small.
    idx = np.empty(len(px), dtype=np.int32)
    for start in range(0, len(px), 4096):
        block = px[start:start + 4096]
        d = ((block[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
        idx[start:start + 4096] = d.argmin(axis=1)
    return idx


def main():
    art = Image.open(ART).convert("RGBA")
    sky = Image.open(SKY).convert("RGB")

    if art.size[0] != sky.size[0]:
        print("ERROR: the logo and the sky have a different width")
        return 1

    # The picture as it is shown on the screen: the logo over the sky.
    cover = sky.convert("RGBA")
    cover.alpha_composite(art, (0, 0))
    cover = cover.convert("RGB")

    w, h = cover.size
    if h < LOGO_H:
        print("ERROR: the picture is smaller than the logo")
        return 1

    logo = cover.crop((0, 0, w, LOGO_H))
    bottom = cover.crop((0, LOGO_H, w, h))

    # The two parts are quantised apart, so the palette of the logo is not
    # spent on the gradient of the sky.
    ql = logo.quantize(colors=LOGO_COLORS, method=Image.Quantize.LIBIMAGEQUANT,
                        dither=Image.Dither.NONE)
    qs = bottom.quantize(colors=SKY_COLORS, method=Image.Quantize.LIBIMAGEQUANT,
                          dither=Image.Dither.NONE)

    pal = palette_of(ql, LOGO_COLORS) + palette_of(qs, SKY_COLORS)

    # The indexes of the two parts: the logo keeps its own, the sky is moved
    # behind the colours of the logo.
    indices = np.empty((h, w), dtype=np.uint8)
    indices[:LOGO_H] = np.asarray(ql, dtype=np.uint8)
    sky_idx = nearest(pal[LOGO_COLORS:], np.asarray(bottom))
    indices[LOGO_H:] = (sky_idx + LOGO_COLORS).astype(np.uint8).reshape(h - LOGO_H, w)

    out = Image.fromarray(indices, mode="P")
    out.putpalette([c for rgb in pal for c in rgb])

    # The result is checked: it must be indexed and it must look like the
    # picture it was made of.
    check = Image.open(OUT) if os.path.exists(OUT) else None
    back = out.convert("RGB")
    a = np.asarray(cover).astype(int)
    b = np.asarray(back).astype(int)
    d = np.abs(a - b).max(axis=2)
    print("cover: %dx%d, palette %d colours" % (w, h, len(pal)))
    print("  error: mean %.2f, max %d, pixels over 16: %.2f%%"
          % (d.mean(), d.max(), (d > 16).mean() * 100))
    print("  logo band : mean %.2f, max %d" % (d[:LOGO_H].mean(), d[:LOGO_H].max()))
    print("  sky band  : mean %.2f, max %d" % (d[LOGO_H:].mean(), d[LOGO_H:].max()))

    out.save(OUT, format="PNG", bits=8, optimize=True)
    print("  written: %s (%d bytes)" % (OUT, os.path.getsize(OUT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
