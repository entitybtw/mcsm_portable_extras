#!/usr/bin/env python3
"""
Builds the pictures of the screens before the title (assets/ui/intro); the
texts of those screens are in the ui_strings of every language:

  headphones.png  the headphones of the mobile game (ui_boot_headphones of
                  ui_boot.scene), as high as on the screen of the old intro

    python3 tools/bake_intro.py <folder of the ui_boot textures as PNG>
"""

import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "ui", "intro")
TEX = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

HEADPHONES_H = 132


def save_t8(im, name, colours=256):
    # Fully transparent pixels share one colour, so they take one entry.
    a = np.asarray(im).copy()
    a[a[..., 3] == 0] = 0
    im = Image.fromarray(a, "RGBA")
    out = im.quantize(colours, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = out.getpalette("RGBA")
    out.putpalette([pal[i] for i in range(len(pal)) if i % 4 != 3])
    out.save(os.path.join(OUT, name), transparency=bytes(pal[3::4]))
    print(name, im.size)


# The headphones: the drawn part of the texture, made smaller with a box filter
# (its big square pixels keep their edges, just smoothed).
t = Image.open(os.path.join(TEX, "ui_boot_headphones.png")).convert("RGBA")
t = t.crop(t.getchannel("A").getbbox())
w = round(t.width * HEADPHONES_H / t.height)
save_t8(t.resize((w, HEADPHONES_H), Image.BOX), "headphones.png", 64)
