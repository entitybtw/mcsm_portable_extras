#!/usr/bin/env python3
"""
Takes the sources of the title screen out of the game and out of the old title
video, into tools/title_src:

  assets/ui/title/clouds.msh  the cloud mesh of ui_boot_clouds.d3dmesh, lit
  sky_keys.png    the colour of the sky by rows, one column per key
  keys.json       the times of the keys, the colour of the clouds and the
                  tint of the landscape at every key

The sky, the clouds and the landscape change from night to day in the first
ten seconds (ui_boot_legal.chore). The chore drives lights and blends that are
only known by hashes, so the colours are measured on the frames of the
recorded screen instead.

    python3 tools/extract_title.py <ui_boot folder> [mcsm_title.pmp]

Without the video only the clouds are made. The video (the old title screen,
assets/ui/mcsm_title.pmp) is no longer in the game; it is in the history of
the repository. The sky keys of the repository
were corrected afterwards, row by row, against the frames of the video (a
render of the sky in PPSSPP compared with them), so the video run would undo
that. The top 14 rows of the day keys (18 to 24) were measured through the
clouds of the video and came out lighter than the sky under them: they were
made again from the row under them, darkening upwards as in key 17.

The ui_boot folder holds ui_boot_clouds.d3dmesh, ui_boot_vignette.png and
ui_boot_landscape.png (the textures converted to PNG).
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "title_src")
BOOT = sys.argv[1]
PMP = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT, exist_ok=True)

# The keys: every 0.4 s up to the full day.
KEY_STEP, KEY_COUNT = 0.4, 25
# The vignette of the scene darkens the corners by this much of its alpha.
VIGNETTE = 0.67


def png(name):
    for d in (BOOT, os.path.join(BOOT, "png")):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise SystemExit("missing " + name)


# --- The clouds ---------------------------------------------------------------
# The cloud layer is one flat slab (y 30..34). Its vertices are 20 bytes apart
# (position first), its triangles a list of 16-bit indices.
mesh = open(os.path.join(BOOT, "ui_boot_clouds.d3dmesh"), "rb").read()


def is_cloud(o):
    x, y, z = struct.unpack("<3f", mesh[o:o + 12])
    return 29.9 < y < 34.1 and -151 < x < 133 and -60 < z < 63


start = next(o for o in range(len(mesh) - 200)
             if all(is_cloud(o + 20 * k) for k in range(8)))
verts, normals = [], []
o = start
while o + 20 <= len(mesh) and is_cloud(o):
    verts.append(struct.unpack("<3f", mesh[o:o + 12]))
    # The normal follows the position as three signed 16-bit numbers. The
    # normals are smoothed over the corners of the boxes: lit, the clouds are
    # white in the middle and get darker towards their edges.
    normals.append([v / 32767 for v in struct.unpack("<3h", mesh[o + 12:o + 18])])
    o += 20
n = len(verts)
# The second stream of the vertices, at the end of the file: 8 bytes each, the
# u, v as half floats and an RGBA colour. Its alpha is the shape of the
# clouds: 248 on the underside (y = 30), 0 on every vertex above it, so the
# sides fade from the underside up into the sky.
second = mesh[len(mesh) - 8 * n:]
alphas = [second[8 * i + 7] for i in range(n)]
best = (0, 0)
o = 0
while o < start:
    p = o
    while p + 2 <= start and struct.unpack("<H", mesh[p:p + 2])[0] < n:
        p += 2
    if (p - o) // 2 > best[0]:
        best = ((p - o) // 2, o)
    o = p + 2 if p > o else o + 1
count, at = best
idx = struct.unpack("<%dH" % count, mesh[at:at + 2 * count])
# The list starts after a few words of its header: the alignment with no
# degenerate triangles is the right one.
shift = min(range(6), key=lambda s: sum(
    1 for i in range(s, count - 2, 3)
    if len({idx[i], idx[i + 1], idx[i + 2]}) < 3))
# The mesh for the engine (Mesh.load): the colour of a vertex is its light,
# white where the normal points down (the undersides the camera sees) and
# bluish on the sides; the GE interpolates it over the faces, like the smooth
# light of the game.
WHITE = np.array([255, 255, 255])
SIDE = np.array([176, 196, 232])
tris = [idx[i:i + 3] for i in range(shift, count - 2, 3)]


def colour(i):
    n = normals[i]
    length = max(1e-6, (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5)
    down = max(0.0, -n[1] / length)
    r, g, b = (SIDE + (WHITE - SIDE) * down).round().astype(int)
    return (alphas[i] << 24) | (b << 16) | (g << 8) | r


# The camera sees only a part of the slab of the clouds (a sixth of it on
# average): the triangles are sorted into tiles of TILE units, by rows of z
# from the far one, then by x, and title.lua draws only the tiles in view (the
# ranges of Mesh.draw). A tile is the triangles whose middle is in it; its box
# is the box of their vertices.
TILE = (30.0, 15.0)     # x, z


def tiles_of(faces):
    keyed = {}
    for t in faces:
        cx = sum(verts[i][0] for i in t) / 3
        cz = sum(verts[i][2] for i in t) / 3
        keyed.setdefault((int((cz + 60) // TILE[1]), int((cx + 151) // TILE[0])), []).append(t)
    return [keyed[k] for k in sorted(keyed)]


def write_mesh(path, faces):
    """Writes the mesh with its triangles in tiles and returns the tiles:
    (first index, index count, x min, x max, y min, z min, z max)."""
    tiles = tiles_of(faces)
    faces = [t for tile in tiles for t in tile]
    # Only the vertices of these faces, in their first order.
    used = sorted({i for t in faces for i in t})
    new = {old: k for k, old in enumerate(used)}
    with open(path, "wb") as out:
        out.write(b"MSH1" + struct.pack("<III", len(used), 3 * len(faces), 0))
        for i in used:
            out.write(struct.pack("<I3f", colour(i), *verts[i]))
        for t in faces:
            out.write(struct.pack("<3H", *(new[i] for i in t)))
    print("mesh:", path, len(used), "vertices,", len(faces), "triangles,", len(tiles), "tiles")
    boxes, first = [], 0
    for tile in tiles:
        p = [verts[i] for t in tile for i in t]
        boxes.append((first, 3 * len(tile), min(v[0] for v in p), max(v[0] for v in p),
                      min(v[1] for v in p), min(v[2] for v in p), max(v[2] for v in p)))
        first += 3 * len(tile)
    return boxes


def lua_tiles(name, boxes):
    rows = ",\n".join("\t\t{ %d, %d, %g, %g, %g, %g, %g }" % b for b in boxes)
    return "\t%s = {\n%s,\n\t},\n" % (name, rows)


# Two meshes: the undersides (y = 30) take the light of the sun, the sides
# the light of the sky; at dusk only the undersides stand out of the sky.
title_dir = os.path.join(ROOT, "assets", "ui", "title")
os.makedirs(title_dir, exist_ok=True)
under = [t for t in tris if all(verts[i][1] < 30.5 for i in t)]
sides = [t for t in tris if not all(verts[i][1] < 30.5 for i in t)]
under_tiles = write_mesh(os.path.join(title_dir, "clouds_under.msh"), under)
side_tiles = write_mesh(os.path.join(title_dir, "clouds.msh"), sides)
with open(os.path.join(title_dir, "clouds_tiles.lua"), "w") as out:
    out.write("-- The tiles of the cloud meshes (tools/extract_title.py): first index,\n"
              "-- index count, x min, x max, y min, z min, z max, in the units of the mesh.\n"
              "return {\n" + lua_tiles("under", under_tiles) + lua_tiles("sides", side_tiles) + "}\n")
print("clouds:", len(verts), "vertices,", (count - shift) // 3, "triangles")

if PMP is None:
    sys.exit(0)

# --- The colours of the first seconds -----------------------------------------
# The video stream of the PMP is a plain H.264 stream: the packets are joined
# and decoded by ffmpeg.
tmp = tempfile.mkdtemp()
f = open(PMP, "rb")
head = struct.unpack("<14I", f.read(56))
frames, streams = head[3], head[9]
index = struct.unpack("<%dI" % frames, f.read(4 * frames))
with open(os.path.join(tmp, "v.h264"), "wb") as out:
    for i in index[:int(30 * (KEY_COUNT * KEY_STEP + 1))]:
        pkt = f.read(i >> 1)
        na = pkt[0]
        fields = struct.unpack("<%dI" % (na * streams + 3), pkt[1:1 + 4 * (na * streams + 3)])
        off = 1 + 4 * (na * streams + 3)
        out.write(pkt[off:off + fields[2]])
fps = head[7] / head[6]
step = round(KEY_STEP * fps)
subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-f", "h264", "-r", str(fps), "-i",
                os.path.join(tmp, "v.h264"), "-vf",
                "select='not(mod(n\\,%d))'" % step, "-fps_mode", "vfr",
                os.path.join(tmp, "k%03d.png")], check=True)

vig = np.asarray(Image.open(png("ui_boot_vignette.png")).getchannel("A")
                 .resize((480, 272), Image.BOX)).astype(float) / 255
lt = Image.open(png("ui_boot_landscape.png")).convert("RGBA")
land = Image.new("RGBA", (1920, 512))
land.paste(lt.crop((128, 512, 1024, 1024)), (0, 0))
land.paste(lt.crop((0, 0, 1024, 512)), (896, 0))
land = np.asarray(land.resize((488, 130), Image.BOX)).astype(float)[:, 4:484]
land_mask = land[..., 3] > 240

# The sky ends behind the trees: lower rows keep the last row of open sky.
SKY_ROWS = 186
sky, clouds, tint = [], [], []
for k in range(KEY_COUNT):
    a = np.asarray(Image.open(os.path.join(tmp, "k%03d.png" % (k + 1))).convert("RGB")).astype(float)
    a = a / np.maximum(1 - vig[..., None] * VIGNETTE, 0.05)
    col = np.zeros((272, 3))
    for y in range(272):
        row = a[min(y, SKY_ROWS)]
        bright = row.sum(1)
        col[y] = np.median(row[bright <= np.percentile(bright, 25)], 0)
    # The text of the logos leaves thin lines: the sky is smoothed by rows.
    pad = np.pad(col, ((6, 6), (0, 0)), mode="edge")
    col = np.array([np.median(pad[y:y + 13], 0) for y in range(272)])
    sky.append(col)
    top = a[0:60].reshape(-1, 3)
    bright = top.sum(1)
    clouds.append(np.median(top[bright >= np.percentile(bright, 92)], 0))
    reg = a[142:272]
    tint.append(np.median(reg[land_mask] / np.maximum(land[..., :3][land_mask], 8), 0))

# One column per key, 4 pixels wide (a linear filter never reaches the next
# key), one row per 4 lines of the screen.
# The keys in the repository were corrected against the video: they are made
# again only on request.
KEEP = os.path.exists(os.path.join(OUT, "sky_keys.png")) and not os.environ.get("TITLE_REDO_KEYS")
img = np.zeros((68, 4 * KEY_COUNT, 3))
for k in range(KEY_COUNT):
    img[:, 4 * k:4 * k + 4] = sky[k][2::4][:68, None, :]
if not KEEP:
    Image.fromarray(img.clip(0, 255).round().astype("uint8")).save(os.path.join(OUT, "sky_keys.png"))

# --- The music ----------------------------------------------------------------
# The audio of the PMP is raw AAC (LC, 44.1 kHz, stereo): every frame gets an
# ADTS header and ffmpeg decodes it. atracdenc (github.com/dcherednik/atracdenc,
# in the PATH or in $ATRACDENC) makes ATRAC3 of it: the PSP decodes it in
# hardware. LP4 (66 kbit/s) is the smallest rate, the engine keeps the whole
# file in memory (~2.7 MB for the 5.5 minutes).
def adts(length):
    full = length + 7
    return bytes([0xFF, 0xF1, (1 << 6) | (4 << 2), (2 << 6) | (full >> 11),
                  (full >> 3) & 0xFF, ((full & 7) << 5) | 0x1F, 0xFC])


f.seek(56 + 4 * frames)
with open(os.path.join(tmp, "a.aac"), "wb") as out:
    for i in index:
        pkt = f.read(i >> 1)
        na = pkt[0]
        fields = struct.unpack("<%dI" % (na * streams + 3), pkt[1:1 + 4 * (na * streams + 3)])
        off = 1 + 4 * (na * streams + 3) + fields[2]
        for k in range(na):
            out.write(adts(fields[3 + k]) + pkt[off:off + fields[3 + k]])
            off += fields[3 + k]
wav = os.path.join(tmp, "music.wav")
subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-i", os.path.join(tmp, "a.aac"),
                "-ar", "44100", "-ac", "2", "-sample_fmt", "s16", wav], check=True)
encoder = os.environ.get("ATRACDENC") or shutil.which("atracdenc")
music = os.path.join(ROOT, "assets", "ui", "title", "music.at3")
if encoder:
    os.makedirs(os.path.dirname(music), exist_ok=True)
    subprocess.run([encoder, "-e", "atrac3_lp4", "-i", wav, "-o", music], check=True)
    print("music:", music)
else:
    print("music: no atracdenc, the WAV is at", wav)

if not KEEP:
    json.dump({
        "step": KEY_STEP,
        "clouds": [[int(min(255, round(v))) for v in c] for c in clouds],
        "tint": [[round(min(1.0, float(v)), 3) for v in t] for t in tint],
    }, open(os.path.join(OUT, "keys.json"), "w"), indent=1)
print("keys:", "kept" if KEEP else "%d every %s s" % (KEY_COUNT, KEY_STEP))
