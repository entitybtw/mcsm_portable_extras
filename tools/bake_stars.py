#!/usr/bin/env python3
"""
Bakes assets/ui/title/stars.png, the stars of the night of the title screen
(ui_boot_stars): a piece of the star texture of the game at its own size, white
with the light in the alpha, 16 levels, 8 bit with a palette.

The stars of the original are not still: the sky turns, and they drift down
and a little to the right (title.lua, STARS), so the picture is taller and
wider than the screen: 500 x 377 pixels (the screen is 480 x 272, the drift is
about 21 px/s for 5 s down and 3.4 px/s to the right).

    python3 tools/bake_stars.py <ui_boot_stars.png> <assets/ui/title/stars.png>
"""
import sys
import numpy as np
from PIL import Image

W, H = 500, 377
U0, V0 = 262, 0          # the piece of the texture (1024 x 1024)

st = np.asarray(Image.open(sys.argv[1]).convert("RGBA")).astype(float)
lum = (st[..., :3].mean(2) / 255 * st[..., 3] / 255)[V0:V0 + H, U0:U0 + W]
light = Image.fromarray((lum * 255).clip(0, 255).astype("uint8")).point(lambda v: (v // 16) * 17)
stars = Image.merge("RGBA", [Image.new("L", light.size, 255)] * 3 + [light])
px = stars.load()
for y in range(stars.height):
    for x in range(stars.width):
        if px[x, y][3] == 0:
            px[x, y] = (0, 0, 0, 0)
out = stars.quantize(16, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
pal = out.getpalette("RGBA")
out.putpalette([pal[i] for i in range(len(pal)) if i % 4 != 3])
out.save(sys.argv[2], transparency=bytes(pal[3::4]))
print(sys.argv[2], stars.size, "T8", sum(1 for p in light.get_flattened_data() if p))
