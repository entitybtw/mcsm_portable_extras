#!/usr/bin/env python3
"""
Builds assets/ui/menu-spritesheet.png from clean sources:

  tools/sheet_src/base.png  the sprites of the game that the code uses
  the floppy of the empty save cards (tools/saves_src/floppy.png)
  tools/epmenu_src          the arrows of the episode menu
  the small hint buttons of the episode menu (from the big ones)
  the check mark of the save screen (the folder of the original textures)

The rows stand without gaps (512x136), and x 0..207, y 90..135 is free for new
sprites. The engine keeps only the rows of a
picture, so every empty row would be 512 bytes of memory. The sheet is stored
as an indexed PNG (T8).

    python3 tools/bake_spritesheet.py <the folder of the original textures>

Keep the cells in sync with assets/misc/savefiles.lua and epmenu.lua.
"""

import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, "assets", "ui", "menu-spritesheet.png")
SRC = os.path.join(ROOT, "tools")

sheet = Image.open(os.path.join(SRC, "sheet_src", "base.png")).convert("RGBA")

# The check mark of the game: its art is 9x8 pixels. It is read back on that grid
# with a hard mask and doubled, so it has no half transparent pixels.
check = Image.open(os.path.join(sys.argv[1], "ui_popupSaveButton_checkMark.png")).convert("RGBA")
check = check.crop(check.getbbox()).resize((9, 8), Image.BOX)
check.putalpha(check.getchannel("A").point(lambda a: 255 if a > 127 else 0))
sheet.paste(check.resize((18, 16), Image.NEAREST), (36, 56))

# The original arrows. One pixel of the art is 6 pixels of the texture, so the
# art is 10x15: it is cut back to its own grid and doubled.
ARROWS = {
    (54, 56): "ui_arrowLeft.png",
    (76, 56): "ui_arrowRight.png",
    (98, 56): "ui_arrowLeftSelected.png",
    (120, 56): "ui_arrowRightSelected.png",
}
for (x, y), name in ARROWS.items():
    art = Image.open(os.path.join(SRC, "epmenu_src", name)).convert("RGBA")
    art = art.crop(art.getbbox()).resize((10, 15), Image.NEAREST)
    sheet.paste(art.resize((20, 30), Image.NEAREST), (x, y))

# The frames of the save cards: the rings of the frame of the game, drawn as
# pixel art with the colours of the buttons of the menus. Every ring is
# (top and left colour, bottom and right colour), from the outside.
W, H = 150, 76
BLACK = (0, 0, 0)
PURPLE, YELLOW = (113, 113, 220), (254, 254, 153)
FRAME_SELECTED = [(BLACK, BLACK), ((166, 166, 234), (92, 92, 186)), (PURPLE, PURPLE),
                  (PURPLE, PURPLE), (YELLOW, YELLOW), (YELLOW, YELLOW)]


def frame(rings):
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for i, (lit, shade) in enumerate(rings):
        for x in range(i, W - i):
            out.putpixel((x, H - 1 - i), shade + (255,))
        for y in range(i, H - i):
            out.putpixel((W - 1 - i, y), shade + (255,))
        for x in range(i, W - i):
            out.putpixel((x, i), lit + (255,))
        for y in range(i, H - i):
            out.putpixel((i, y), lit + (255,))
    return out


sheet.paste(frame(FRAME_SELECTED), (208, 56))


def button_frame():
    # The plain frame is the sprite of the plain button itself: its edges are
    # stretched around the hole, with a black line inside. T is the thickness.
    t = 6
    btn = sheet.crop((184, 1, 365, 24))
    bw, bh = btn.size
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(btn.crop((0, 0, bw, t)).resize((W, t), Image.NEAREST), (0, 0))
    out.paste(btn.crop((0, bh - t, bw, bh)).resize((W, t), Image.NEAREST), (0, H - t))
    side = H - t * 2
    out.paste(btn.crop((0, t, t, bh - t)).resize((t, side), Image.NEAREST), (0, t))
    out.paste(btn.crop((bw - t, t, bw, bh - t)).resize((t, side), Image.NEAREST), (W - t, t))
    # The frame stands on a light panel, so it is lighter than the button.
    px = out.load()
    for yy in range(H):
        for xx in range(W):
            r, g, b, a = px[xx, yy]
            if a:
                px[xx, yy] = (min(255, r * 13 // 10), min(255, g * 13 // 10),
                              min(255, b * 13 // 10), a)
    i = t - 1
    for x in range(i, W - i):
        out.putpixel((x, i), BLACK + (255,))
        out.putpixel((x, H - 1 - i), BLACK + (255,))
    for y in range(i, H - i):
        out.putpixel((i, y), BLACK + (255,))
        out.putpixel((W - 1 - i, y), BLACK + (255,))
    return out


sheet.paste(button_frame(), (360, 56))

# The floppy of an empty card: the floppy of the game that the sheet of commit
# ed360873e had, drawn again on a grid of 17 x 17 cells of 2 x 2 px (the old
# one was the texture made smaller by an odd factor: lines of 1 and 2 px and
# half-transparent edges). Kept as tools/saves_src/floppy.png (34x34).
sheet.paste(Image.new("RGBA", (34, 34), (0, 0, 0, 0)), (0, 90))
floppy = Image.open(os.path.join(SRC, "saves_src", "floppy.png")).convert("RGBA")
sheet.paste(floppy, (0, 90))

# The small buttons of the hints of the episode menu (14x14): the buttons of the
# other menus (20x20, y 26), averaged down. Cross, square, circle, triangle.
for i, src in enumerate((20, 40, 0, 60)):
    icon = sheet.crop((src, 26, src + 20, 46)).resize((14, 14), Image.BOX)
    sheet.paste(icon, (144 + 16 * i, 56))

# The knobs of the sliders (18x26, selected at 262,26 and static at 280,26) are
# made of the button sprites: the 4 px caps (border, bevel) and 10 px of the
# middle (the texture) of the selected button (0,0) and of the static one
# (184,1), both 184x25; the middle row is repeated to make 26 rows.
def knob(src, dst):
    btn = sheet.crop((src[0], src[1], src[0] + 184, src[1] + 25))
    tmp = Image.new("RGBA", (18, 25), (0, 0, 0, 0))
    tmp.paste(btn.crop((0, 0, 4, 25)), (0, 0))
    tmp.paste(btn.crop((87, 0, 97, 25)), (4, 0))
    tmp.paste(btn.crop((180, 0, 184, 25)), (14, 0))
    k = Image.new("RGBA", (18, 26), (0, 0, 0, 0))
    k.paste(tmp.crop((0, 0, 18, 12)), (0, 0))
    k.paste(tmp.crop((0, 12, 18, 13)), (0, 12))
    k.paste(tmp.crop((0, 12, 18, 25)), (0, 13))
    sheet.paste(Image.new("RGBA", (18, 26), (0, 0, 0, 0)), dst)
    sheet.paste(k, dst)


knob((0, 0), (262, 26))
knob((184, 1), (280, 26))

# Fully transparent pixels all get one colour, so they take one palette entry.
px = sheet.load()
for yy in range(sheet.height):
    for xx in range(sheet.width):
        if px[xx, yy][3] == 0:
            px[xx, yy] = (0, 0, 0, 0)

# The T8 palette. The cells of EXACT keep their own colours: the quantizer would
# shift the greys of the save screen.
EXACT = [(0, 90, 34, 34), (208, 56, 150, 76), (360, 56, 150, 76)]
exact = {}
for x, y, w, h in EXACT:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            c = px[xx, yy]
            if c[3] and c not in exact:
                exact[c] = len(exact)
if len(exact) > 200:
    raise SystemExit("too many exact colours: %d" % len(exact))
base = 256 - len(exact)
out = sheet.quantize(base, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
pal = out.getpalette("RGBA")
pal += [0] * (base * 4 - len(pal))
for c in exact:
    pal += list(c)
idx = out.load()
for x, y, w, h in EXACT:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            c = px[xx, yy]
            if c[3]:
                idx[xx, yy] = base + exact[c]
out.putpalette(pal[i] for i in range(len(pal)) if i % 4 != 3)
out.save(SHEET, optimize=False, transparency=bytes(pal[3::4]))
print(SHEET, out.mode, len(exact), "exact colours")
