#!/usr/bin/env python3
"""
Makes the music of the title screen (assets/ui/title/music.at3) from the music
of the original game.

The title screen plays the FMOD event of audio_music_interface_ui_boot: the
sound noMoreCreepersLinear126_01 of Menu.bank (MCSM_pc_Menu_ms.ttarch2), 377 s.
It matches the sound of the recorded title screen (the mus_loop_boot.wav of the
boot archive is another music). The timeline of the event has two markers,
"loop begins" (95.2 s) and "outro" (369.5 s), and a transition region between
them that goes back to "loop begins": the beginning is played once, then the
part between the markers loops; the outro is only played on a change of a
parameter (the title screen never asks for it: titleHide silences the music).

Menu.bank holds an FMOD sound bank (FSB5, Vorbis): the sound is rebuilt as Ogg
by the fsb5 package (pip install fsb5), resampled to 44.1 kHz by ffmpeg, cut at
"outro" and encoded by atracdenc (github.com/dcherednik/atracdenc, in the PATH
or in $ATRACDENC) as ATRAC3 LP4 (66 kbit/s, ~3 MB, the engine keeps the file in
memory). A smpl chunk with the markers loops it in sceAtrac, without a gap.

    python3 tools/make_title_music.py <Menu.bank from the archive>
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave

import fsb5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "ui", "title", "music.at3")
SOUND = "noMoreCreepersLinear126_01"
RATE = 44100


def chunks(b):
    p = 12
    while p + 8 <= len(b):
        cid, size = b[p:p + 4], struct.unpack("<I", b[p + 4:p + 8])[0]
        yield cid, p, size
        p += 8 + size + (size & 1)


def add_loop(at3, start, end):
    b = bytearray(open(at3, "rb").read())
    delay = 0
    for cid, p, size in chunks(b):
        if cid == b"fact" and size >= 8:
            delay = struct.unpack("<I", b[p + 12:p + 16])[0]
            # The length is the samples of the sound, without the delay of
            # the encoder (atracdenc writes all the frames): with more, the
            # frames of the data do not cover it and sceAtrac refuses the file.
            struct.pack_into("<I", b, p + 8, end)
    # The loop is counted from the first sample of the stream, the delay of
    # the encoder included.
    smpl = struct.pack("<9I", 0, 0, 1000000000 // RATE, 60, 0, 0, 0, 1, 0)
    smpl += struct.pack("<6I", 0, 0, start + delay, end + delay - 1, 0, 0)
    # The smpl chunk goes before the data, where sceAtrac reads it.
    for cid, p, size in chunks(b):
        if cid == b"data":
            b[p:p] = b"smpl" + struct.pack("<I", len(smpl)) + smpl
            break
    struct.pack_into("<I", b, 4, len(b) - 8)
    open(at3, "wb").write(b)
    return delay


def find_in_chunk(bank, data, kind, start=0):
    """The first place of data inside a chunk of this kind, and that chunk."""
    i = bank.find(data, start)
    while i >= 0:
        head = bank.rfind(kind, max(0, i - 256), i)
        if head >= 0:
            size = struct.unpack("<I", bank[head + 4:head + 8])[0]
            if i + len(data) <= head + 8 + size:
                return i, bank[head + 8:head + 8 + size]
        i = bank.find(data, i + 1)
    raise SystemExit("nothing found in a %s chunk" % kind.decode())


def markers(bank, index):
    """The markers of the timeline that plays the sound number index:
    WAV chunk (its GUID, then u32 8, u16 0, u32 the number of the sound) ->
    waveform instrument (WAIB: its GUID, a flag, the GUID of the WAV) -> the
    timeline (TLNB) that holds the instrument, with its markers: GUID, place
    (u32, samples of the sound), length of the name (u16), name."""
    _, wav = find_in_chunk(bank, struct.pack("<IHI", 8, 0, index), b"WAV ")
    _, waib = find_in_chunk(bank, wav[:16], b"WAIB")
    _, timeline = find_in_chunk(bank, waib[:16], b"TLNB")
    found = []
    for name in (b"loop begins", b"outro"):
        k = timeline.find(struct.pack("<H", len(name)) + name)
        if k < 0:
            raise SystemExit("no marker " + name.decode())
        found.append(struct.unpack("<I", timeline[k - 4:k])[0])
    return found


def main():
    bank = open(sys.argv[1], "rb").read()
    fsb = fsb5.FSB5(bank[bank.find(b"FSB5"):])
    index = next(k for k, s in enumerate(fsb.samples) if s.name.split(" {")[0] == SOUND)
    sample = fsb.samples[index]
    begin, outro = markers(bank, index)
    enc = os.environ.get("ATRACDENC") or shutil.which("atracdenc")
    if not enc:
        raise SystemExit("atracdenc is not found (PATH or $ATRACDENC)")
    tmp = tempfile.mkdtemp()
    ogg = os.path.join(tmp, "music.ogg")
    open(ogg, "wb").write(fsb.rebuild_sample(sample))
    pcm = os.path.join(tmp, "music.wav")
    subprocess.run(["ffmpeg", "-v", "quiet", "-y", "-i", ogg, "-af",
                    "aresample=%d:resampler=soxr:precision=28" % RATE, "-ac", "2",
                    "-c:a", "pcm_s16le", pcm], check=True)
    start = round(begin * RATE / sample.frequency)
    length = round(outro * RATE / sample.frequency)
    w = wave.open(pcm)
    frames = w.readframes(length)
    w.close()
    # sceAtrac wants more frames in the data than the length asks for: 2048
    # samples of silence after the end, never played (the loop ends before).
    w = wave.open(pcm, "wb")
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(RATE)
    w.writeframes(frames + bytes(4 * 2048))
    w.close()
    # atracdenc counts the kilobits by 1024: 64 gives the frames of 192 bytes
    # of LP4.
    subprocess.run([enc, "-e", "atrac3", "--container", "riff", "--bitrate", "64",
                    "-i", pcm, "-o", OUT], check=True, stdout=subprocess.DEVNULL)
    delay = add_loop(OUT, start, length)
    print(OUT, os.path.getsize(OUT), "bytes, loop", start / RATE, "..", length / RATE,
          "s, delay", delay)


main()
