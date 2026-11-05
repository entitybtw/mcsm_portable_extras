#!/usr/bin/env python3
"""
Converts the pictures of the port to the formats the PSP can store in the
least memory: the indexed ones (T8/T4, that is a palette of 256 or 16
colours) and the 16-bit ones (5650).

The engine (libs/g2d/glib2d.c) decides the format of a texture by the
format of the PNG itself:

  * PNG_COLOR_TYPE_PALETTE with a bit depth of 8 -> T8 (one byte per pixel)
  * PNG_COLOR_TYPE_PALETTE with a bit depth of 4 -> T4 (two pixels per byte)
  * PNG_COLOR_TYPE_RGB (no alpha)             -> 5650 (two bytes per pixel)
  * anything else                              -> 8888 (four bytes per pixel)

The alpha of an indexed picture is not lost: the engine reads the tRNS
chunk of the PNG and puts the alpha of every colour of the palette into
the CLUT of the texture, so the transparency stays exactly as it was.

The pictures of the video episodes are photographs with tens of thousands
of colours: they are left as they are (the engine loads them as 5650 on
its own, so they are already in the cheapest format that keeps their
quality).

The pictures with a soft alpha (the spritesheet, the art of the episodes,
the icon of the saves, the picture of the controls) keep their alpha
exactly: the palette of the picture simply holds the colours that are
really used, with their own alpha.
"""

import os
import sys
import glob
import shutil
from collections import Counter

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# The root of the project: the paths of the pictures are made relative to
# it, so the temporary copies always stay inside the temporary directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The alpha is not cut: the palette keeps the colours with their own alpha.
# A picture is put into a 4-bit palette only when it is really drawn with
# very few colours, so the quality does not suffer.
MAX_COLORS_8 = 256
MAX_COLORS_4 = 16

# The temporary directory for the converted pictures. It is only used to
# check the result before it replaces the original file.
TMP_OUT = "/tmp/opencode/convert_out"


def alpha_histogram(img):
    return img.getchannel("A").histogram()


def count_colors(img):
    colors = img.getcolors(maxcolors=1 << 24)
    return len(colors) if colors else 1 << 24


def compress_palette(pal_img, colors):
    """Quantizes the picture to a palette, keeping the alpha."""
    return pal_img.quantize(
        colors=colors,
        method=Image.Quantize.LIBIMAGEQUANT,
        dither=Image.Dither.NONE,
    )


def save_png(img, path, bits=8):
    """Saves an indexed picture so that the engine reads it as T8 or T4."""
    if bits == 4:
        img.save(path, format="PNG", bits=4, optimize=True)
    else:
        img.save(path, format="PNG", bits=8, optimize=True)


def convert(path, dry_run=False, verbose=True):
    original = Image.open(path)
    mode = original.mode
    rgba = original.convert("RGBA")

    alpha_hist = alpha_histogram(rgba)
    has_transparent = alpha_hist[0] > 0
    has_partial = sum(alpha_hist[1:255]) > 0
    ncolors = count_colors(rgba)

    # The decision: a picture goes into a palette when it does not have more
    # colours than the palette can hold. A picture with a lot of colours is
    # left alone: the engine loads it as 5650 by itself.
    if ncolors <= MAX_COLORS_4:
        target, bits = MAX_COLORS_4, 4
    elif ncolors <= MAX_COLORS_8:
        target, bits = MAX_COLORS_8, 8
    else:
        if verbose:
            print(f"  {path}: left as it is ({ncolors} colours, the engine "
                  f"loads it as 5650)")
        return None

    quantized = compress_palette(rgba, target)
    # The result is written to a temporary file first. The path of the
    # picture is made relative to the root of the project, so the temporary
    # file always stays inside the temporary directory (os.path.join drops
    # the first part of the path when the second one is absolute).
    rel = os.path.relpath(path, ROOT)
    out = os.path.join(TMP_OUT, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    save_png(quantized, out, bits)

    # The result is checked: the engine must see a palette, and the picture
    # must not have changed too much.
    check = Image.open(out)
    if check.mode != "P":
        print(f"  {path}: ERROR, the result is not indexed")
        return None
    back = check.convert("RGBA")
    a = list(rgba.getdata())
    b = list(back.getdata())
    alpha_bad = sum(1 for x, y in zip(a, b) if x[3] != y[3])
    rgb_bad = sum(
        1
        for x, y in zip(a, b)
        if x[3] > 0 and (x[0] != y[0] or x[1] != y[1] or x[2] != y[2])
    )
    exact = sum(1 for x, y in zip(a, b) if x == y)

    if verbose:
        print(f"  {path}: {mode} -> P{bits} ({target} colours, "
              f"{ncolors} before)  exact={exact * 100 // len(a)}%  "
              f"alpha_diff={alpha_bad}  rgb_diff={rgb_bad}  "
              f"{os.path.getsize(path)} -> {os.path.getsize(out)} bytes")

    if not dry_run:
        shutil.copyfile(out, path)
    return out


def main():
    assets = os.path.join(ROOT, "assets")
    dry = "--dry-run" in sys.argv

    files = sorted(glob.glob(os.path.join(assets, "**", "*.png"), recursive=True))
    # The saves are the data of the player, they are never touched.
    files = [f for f in files if "/saves/" not in f]

    print(f"{len(files)} pictures to convert\n")
    changed = 0
    for path in files:
        before = os.path.getsize(path)
        result = convert(path, dry_run=dry)
        if result:
            changed += 1
    print(f"\n{changed} pictures converted")


if __name__ == "__main__":
    main()
