#!/usr/bin/env python3
"""
Bakes the pictures of the controls screen: the art of the console from
tools/controls_src/ with the yellow lines to the labels.

The art is enlarged 3 times without filtering and the lines are drawn in the
pixels of the art, so they look like a part of it. The result is drawn 1:1 by
assets/misc/controls_text.lua: keep ORIGIN and the LABELS there in sync with
the lines here (screen = ORIGIN + 3 * pixel of the art).

The pictures are saved as indexed PNGs, the cheapest format of the engine.

Run it from anywhere:
    python3 tools/bake_controls.py
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "controls_src")
OUT = os.path.join(ROOT, "assets", "ui", "controls")

SCALE = 3
YELLOW = (251, 233, 3, 255)

# size: the canvas in pixels of the art. Every line is a list of points; its
# parts are horizontal, vertical or at 45 degrees.
MODELS = {
    "psp": {
        "size": (90, 48),
        "lines": [
            [(75, 6), (88, 6)],                       # R
            [(73, 21), (81, 29), (88, 29)],           # the face buttons
            [(60, 34), (69, 43), (78, 43)],           # Start
            [(55, 34), (55, 46)],                     # Select
        ],
    },
    "go": {
        "size": (86, 68),
        "lines": [
            [(79, 33), (82, 30), (85, 30)],           # R (the top of the slider: open, the
                                                      # shoulders stand over the face buttons)
            [(71, 51), (85, 51)],                     # the face buttons
            [(50, 58), (59, 67), (80, 67)],           # Start (the lower bar)
            [(43, 54), (42, 55), (42, 67)],           # Select (the upper bar)
        ],
    },
}


def bake(name, model):
    art = Image.open(os.path.join(SRC, name + ".png")).convert("RGBA")
    canvas = Image.new("RGBA", model["size"], (0, 0, 0, 0))
    canvas.paste(art, (0, 0))

    draw = ImageDraw.Draw(canvas)
    for line in model["lines"]:
        draw.line(line, fill=YELLOW, width=1)

    w, h = canvas.size
    canvas = canvas.resize((w * SCALE, h * SCALE), Image.NEAREST)

    # The palette is built by hand: it keeps every colour with its own alpha.
    colors = sorted(set(canvas.getdata()))
    if len(colors) > 256:
        raise SystemExit(name + ": too many colours")
    index = {c: i for i, c in enumerate(colors)}
    out = Image.new("P", canvas.size)
    out.putdata([index[p] for p in canvas.getdata()])
    pal = []
    for c in colors:
        pal += c[:3]
    out.putpalette(pal)
    path = os.path.join(OUT, name + ".png")
    out.save(path, transparency=bytes(c[3] for c in colors), optimize=False)
    print(path, canvas.size, len(colors), "colours")


for model_name, model_def in MODELS.items():
    bake(model_name, model_def)
