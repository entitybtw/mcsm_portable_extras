#!/usr/bin/env python3
"""
Smooths the colours of the sky of the title screen down the rows.

The colours of the keys of the sky (sky_keys.png, 25 keys of 4 columns, 68 rows)
were measured on frames of a recording, and the noise of its compression is in
them: the gradient of a column goes up and down from a row to the next
(10..30 reversals in 66 rows) and jumps by up to 20 levels, which is seen as
stripes while the sky turns from night to day. Every column is smoothed down the
rows with a gaussian (SIGMA rows, the ends are mirrored) and the keys 1 to 3
(the black of the night) are left as they are.

    python3 tools/smooth_sky.py <sky_keys.png> <out.png> [sigma]
"""
import sys
import numpy as np
from PIL import Image

SIGMA = float(sys.argv[3]) if len(sys.argv) > 3 else 2.5
im = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(float)   # 68 x 100 x 3
h = im.shape[0]
r = int(SIGMA * 3)
kernel = np.exp(-0.5 * (np.arange(-r, r + 1) / SIGMA) ** 2)
kernel /= kernel.sum()
out = im.copy()
for x in range(im.shape[1]):
    if x < 12:       # keys 1..3: the black of the night, nothing to smooth
        continue
    for c in range(3):
        col = np.pad(im[:, x, c], r, mode="reflect")
        out[:, x, c] = np.convolve(col, kernel, mode="valid")
res = Image.fromarray(np.rint(out).clip(0, 255).astype("uint8"))
res.save(sys.argv[2])
d = np.abs(out - im)
print("max change", round(float(d.max()), 1), "mean", round(float(d.mean()), 2))
