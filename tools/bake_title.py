#!/usr/bin/env python3
"""
Builds the pictures of the title screen (assets/ui/title) from the textures of
ui_boot.scene and from tools/title_src (made by extract_title.py):

  sky.png       the sky by rows, one 4 pixels wide column per key
  land.png      the landscape, as wide as the screen
  logo.png      the logo of the game
  logos.png     the logos of Telltale and Mojang
  vignette.png  the dark corners, stretched over the screen
  stars.png     the stars of the night, over the sky
  keys.lua      the colour of the clouds, the tint of the landscape and the
                colour of the sky where the clouds end, by keys

The places and sizes were fitted on the frames of the recorded screen.

    python3 tools/bake_title.py <folder of the ui_boot textures as PNG>
"""

import json

import numpy as np
import os
import sys


from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "tools", "title_src")
OUT = os.path.join(ROOT, "assets", "ui", "title")
TEX = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def tex(name):
    return Image.open(os.path.join(TEX, name + ".png")).convert("RGBA")


def save_t8(im, name, colours=256):
    # Fully transparent pixels share one colour, so they take one entry.
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if px[x, y][3] == 0:
                px[x, y] = (0, 0, 0, 0)
    out = im.quantize(colours, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = out.getpalette("RGBA")
    out.putpalette([pal[i] for i in range(len(pal)) if i % 4 != 3])
    out.save(os.path.join(OUT, name), transparency=bytes(pal[3::4]))
    print(name, im.size, "T8")


# The logo: two quads of the scene take 768 x 512 each, from the two halves of
# the texture.
t = tex("ui_boot_title")
logo = Image.new("RGBA", (1536, 512))
logo.paste(t.crop((256, 0, 1024, 512)), (0, 0))
logo.paste(t.crop((0, 512, 768, 1024)), (768, 0))
save_t8(logo.resize((388, 129), Image.BOX), "logo.png")

# The landscape: the left quad is the right 896 pixels of the lower half, the
# right quad the whole upper half. On the screen it is 488 wide from x = -4.
t = tex("ui_boot_landscape")
land = Image.new("RGBA", (1920, 512))
land.paste(t.crop((128, 512, 1024, 1024)), (0, 0))
land.paste(t.crop((0, 0, 1024, 512)), (896, 0))
land = land.resize((488, 130), Image.BOX).crop((4, 0, 484, 130))
save_t8(land, "land.png")

# The logos of the first seconds, side by side. The autosave icon is the chest
# of the global spritesheet (title.lua), like the one of the saves.
logos = Image.new("RGBA", (262, 91), (0, 0, 0, 0))
for name, (w, h), x in (("ui_boot_logoTTG", (101, 91), 0), ("ui_boot_logoMojang", (160, 25), 102)):
    im = tex(name)
    im = im.crop(im.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox())
    logos.paste(im.resize((w, h), Image.BOX), (x, 0))
save_t8(logos, "logos.png")

# The stars of the night (ui_boot_stars): a piece of the texture at its own
# size (the video shows few, faint stars), white with the light in the alpha,
# 16 levels.
st = np.asarray(tex("ui_boot_stars")).astype(float)
lum = (st[..., :3].mean(2) / 255 * st[..., 3] / 255)[0:142, 272:752]
light = Image.fromarray((lum * 255).clip(0, 255).astype("uint8")).point(lambda v: (v // 16) * 17)
stars = Image.merge("RGBA", [Image.new("L", light.size, 255)] * 3 + [light])
save_t8(stars, "stars.png", 16)

# The vignette: black, its strength measured on the video.
VIGNETTE = 0.67
a = tex("ui_boot_vignette").getchannel("A").resize((60, 34), Image.BOX)
vig = Image.new("RGBA", a.size, (0, 0, 0, 0))
vig.putalpha(a.point(lambda v: round(v * VIGNETTE)))
vig.save(os.path.join(OUT, "vignette.png"))
print("vignette.png", vig.size)

# The sky as it is.
Image.open(os.path.join(SRC, "sky_keys.png")).convert("RGB").save(os.path.join(OUT, "sky.png"))
print("sky.png")

# The keys, as Lua.
keys = json.load(open(os.path.join(SRC, "keys.json")))
# The fog of the clouds takes the colour of the sky where the clouds end (the
# row 100 of the screen, row 25 of sky.png).
sky = Image.open(os.path.join(SRC, "sky_keys.png")).convert("RGB")
horizon = [sky.getpixel((4 * k + 1, 25)) for k in range(len(keys["clouds"]))]
# The sides of the near clouds take the colour of the sky behind them at dusk
# (the row 40 of the screen, row 10 of sky.png).
aloft = [sky.getpixel((4 * k + 1, 10)) for k in range(len(keys["clouds"]))]
with open(os.path.join(OUT, "keys.lua"), "w") as f:
    f.write("-- Made by tools/bake_title.py: the clouds and the landscape by keys.\n")
    f.write("return {\n\tstep = %s,\n\tclouds = {\n" % keys["step"])
    for c in keys["clouds"]:
        f.write("\t\t{ %d, %d, %d },\n" % tuple(c))
    f.write("\t},\n\ttint = {\n")
    for c in keys["tint"]:
        f.write("\t\t{ %s, %s, %s },\n" % tuple(c))
    f.write("\t},\n\thorizon = {\n")
    for c in horizon:
        f.write("\t\t{ %d, %d, %d },\n" % tuple(c))
    f.write("\t},\n\taloft = {\n")
    for c in aloft:
        f.write("\t\t{ %d, %d, %d },\n" % tuple(c))
    f.write("\t},\n}\n")
print("keys.lua")
