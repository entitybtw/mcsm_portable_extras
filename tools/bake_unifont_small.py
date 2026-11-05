#!/usr/bin/env python3
"""
Makes a small pixel version of unifont on a grid of its own, as crisp as the
minecraft font at 8 px.

unifont is drawn on a grid of 16 rows (its glyphs are 8 or 16 pixels wide), so at
any other size its pixels fall between the pixels of the screen and the letters
are blurry. Here every glyph is rasterized at 16 px (exact), reduced to H rows
(the buckets of 16/H pixels, a pixel is on when at least THRESHOLD of its bucket
is ink) and written as a TrueType font whose design pixel is PPU units, so loaded at
the size H (1 design pixel = 1 screen pixel) it is on the grid of the screen.

    python3 tools/bake_unifont_small.py <unifont.ttf> <out.ttf> <H> [threshold] [reduce|trim] [horizontal scale] [prop|fixed]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

SRC, OUT, H = sys.argv[1], sys.argv[2], int(sys.argv[3])
THRESHOLD = float(sys.argv[4]) if len(sys.argv) > 4 else 0.4
PPU = 128
MODE = sys.argv[5] if len(sys.argv) > 5 else 'trim'
PROPORTIONAL = (sys.argv[7] if len(sys.argv) > 7 else 'prop') == 'prop'
SX = float(sys.argv[6]) if len(sys.argv) > 6 else H / 16     # the horizontal scale (letters can be wider than tall)
ASC16 = 14                      # rows of unifont above the baseline (2 below)
asc = max(1, round(ASC16 * H / 16))

ranges = list(range(0x20, 0x7F)) + list(range(0xA0, 0x100)) + [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2116] \
    + list(range(0x400, 0x460)) + [0x490, 0x491]
f16 = ImageFont.truetype(SRC, 16)
cmapsrc = {}
from fontTools.ttLib import TTFont
cm = TTFont(SRC).getBestCmap()


def glyph16(ch):
    adv = int(round(f16.getlength(ch)))
    W = max(adv, 1) + 8
    im = Image.new("L", (W, 24), 0)
    ImageDraw.Draw(im).text((4, 18), ch, font=f16, fill=255, anchor="ls")
    a = np.asarray(im) > 127
    return a[4:20, 4:4 + max(adv, 1)], adv          # the 16 rows of the cell


def reduce(cell, nw):
    h, w = cell.shape
    out = np.zeros((H, nw), bool)
    for j in range(H):
        ya, yb = round(j * h / H), round((j + 1) * h / H)
        for i in range(nw):
            xa, xb = round(i * w / nw), round((i + 1) * w / nw)
            if xb > xa and yb > ya:
                out[j, i] = cell[ya:yb, xa:xb].mean() >= THRESHOLD
    return out


def reduce_trim(cell, nw_cell):
    """Reduces the ink box of the glyph (its edges stand on the buckets), then puts the
    result where the box was, scaled: the baseline stays and the left edge too."""
    ys, xs = np.nonzero(cell)
    if len(ys) == 0:
        return np.zeros((H, nw_cell), bool)
    t, b, l, r = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sc = H / 16
    nh = max(1, round((b - t) * sc)); nw = max(1, int(np.ceil((r - l) * SX - 0.01)))
    box = cell[t:b, l:r]
    small = np.zeros((nh, nw), bool)
    for j in range(nh):
        ya, yb = round(j * (b - t) / nh), round((j + 1) * (b - t) / nh)
        for i in range(nw):
            xa, xb = round(i * (r - l) / nw), round((i + 1) * (r - l) / nw)
            if yb > ya and xb > xa:
                small[j, i] = box[ya:yb, xa:xb].mean() >= THRESHOLD
    out = np.zeros((H, nw_cell), bool)
    bottom_rel = b - ASC16                         # rows below the baseline (the bottom of the ink)
    new_bottom = asc + round(bottom_rel * sc)      # the row of the bottom edge in the new cell
    top = new_bottom - nh
    left = int(round(l * SX))
    for j in range(nh):
        for i in range(nw):
            yy, xx = top + j, left + i
            if small[j, i] and 0 <= yy < H and 0 <= xx < nw_cell:
                out[yy, xx] = True
    return out


def outline(bm):
    pen = TTGlyphPen(None)
    for r in range(bm.shape[0]):
        for c in range(bm.shape[1]):
            if bm[r, c]:
                ytop, ybot = (asc - r) * PPU, (asc - r - 1) * PPU
                x0, x1 = c * PPU, (c + 1) * PPU
                pen.moveTo((x0, ybot)); pen.lineTo((x1, ybot)); pen.lineTo((x1, ytop)); pen.lineTo((x0, ytop)); pen.closePath()
    return pen.glyph()


glyf, advance, cmap, order = {}, {}, {}, [".notdef"]
glyf[".notdef"] = outline(np.zeros((H, 1), bool)); advance[".notdef"] = (H * PPU // 2, 0)
for cp in ranges:
    if cp not in cm:
        continue
    cell, adv = glyph16(chr(cp))
    nw = max(1, int(round(adv * SX))) if adv else max(1, H // 2)
    name = "uni%04X" % cp
    order.append(name)
    bm = (reduce_trim(cell, nw + 2) if MODE == 'trim' else reduce(cell, nw)) if cell.any() else np.zeros((H, nw), bool)
    if PROPORTIONAL:
        # The width of a letter is its ink and a gap of one pixel, as in the pixel fonts
        # (minecraft.ttf): narrow letters are narrow. A space is a quarter of the cell.
        cols = np.nonzero(bm.any(0))[0]
        nw = int(cols.max()) + 2 if len(cols) else max(2, int(round(adv * SX * 0.5)))
        bm = bm[:, :nw] if bm.shape[1] >= nw else np.pad(bm, ((0, 0), (0, nw - bm.shape[1])))
    glyf[name] = outline(bm)
    advance[name] = (nw * PPU, 0)
    cmap[cp] = name

fb = FontBuilder(H * PPU, isTTF=True)
fb.setupGlyphOrder(order)
fb.setupCharacterMap(cmap)
fb.setupGlyf(glyf)
fb.setupHorizontalMetrics(advance)
fb.setupHorizontalHeader(ascent=asc * PPU, descent=-(H - asc) * PPU)
fb.setupNameTable({"familyName": "UnifontSmall%d" % H, "styleName": "Regular"})
fb.setupOS2(sTypoAscender=asc * PPU, sTypoDescender=-(H - asc) * PPU, usWinAscent=asc * PPU, usWinDescent=(H - asc) * PPU)
fb.setupPost()
fb.save(OUT)
print(OUT, "H", H, "glyphs", len(order), "asc", asc)
