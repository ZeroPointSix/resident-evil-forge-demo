#!/usr/bin/env python3
"""Compose Containment Pulse: original notes and synthesized instruments, no samples.

The score and PCM are deterministic. Ogg container serials may vary by ffmpeg
version; the committed Ogg is the release asset. Requires Python and ffmpeg.
"""

from array import array
import argparse
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import wave

RATE = 44100
SECONDS = 24
BEAT = 60 / 80
ROOTS = (38, 38, 41, 37, 38, 43, 41, 38)
MELODY = ((62, 65, 63, 68), (67, 65, 61, 62), (65, 68, 72, 70),
          (61, 64, 67, 64), (62, 69, 65, 63), (67, 70, 74, 68),
          (65, 63, 68, 61), (62, 65, 69, 62))


def compose() -> array:
    mix = array("d", [0.0]) * (RATE * SECONDS)
    rng = random.Random(20261004)

    def note(start, duration, midi, level, voice):
        offset = round(start * RATE)
        count = min(round(duration * RATE), len(mix) - offset)
        hz = 440 * 2 ** ((midi - 69) / 12)
        for i in range(count):
            t = i / RATE
            phase = 2 * math.pi * hz * t
            attack = min(1, t / 0.012)
            release = min(1, (count - i) / (RATE * 0.08))
            if voice == "bass":
                sound = math.sin(phase) + 0.22 * math.sin(2 * phase) + 0.08 * math.sin(3 * phase)
                envelope = math.exp(-t * 3)
            else:
                sound = math.sin(phase + 1.8 * math.sin(phase * 2) * math.exp(-t * 9))
                sound += 0.18 * math.sin(phase * 3.01) * math.exp(-t * 8)
                envelope = math.exp(-t * 3.7)
            mix[offset + i] += sound * envelope * attack * release * level

    def drum(start, kind, level):
        duration = 0.28 if kind == "kick" else 0.12
        offset = round(start * RATE)
        for i in range(min(round(duration * RATE), len(mix) - offset)):
            t = i / RATE
            if kind == "kick":
                phase = 2 * math.pi * (46 * t + 6 * (1 - math.exp(-t * 30)))
                sound = math.sin(phase) * math.exp(-t * 16)
            else:
                sound = rng.uniform(-1, 1) * math.exp(-t * 65)
            mix[offset + i] += sound * min(1, t / 0.002) * level

    for bar, root in enumerate(ROOTS):
        start = bar * 4 * BEAT
        for beat in (0, 1.5, 2, 3.5):
            note(start + beat * BEAT, 0.7, root, 0.25, "bass")
        for beat, midi in enumerate(MELODY[bar]):
            onset = start + (beat + 0.25) * BEAT
            note(onset, 1.1, midi, 0.12, "bell")
            note(onset + BEAT * 0.5, 0.8, midi, 0.035, "bell")
        for beat in range(4):
            drum(start + beat * BEAT, "kick", 0.27 if beat % 2 == 0 else 0.13)
            drum(start + (beat + 0.5) * BEAT, "hat", 0.06)
    peak = max(abs(v) for v in mix)
    pcm = array("h")
    for i, value in enumerate(mix):
        fade = min(1, i / (RATE * 0.08), (len(mix) - 1 - i) / (RATE * 1.2))
        pcm.append(round(value / peak * 0.76 * fade * 32767))
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(
        "src/main/resources/assets/re_demo/sounds/music/containment_pulse.ogg"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="re-demo-audio-") as temp:
        source = Path(temp) / "containment_pulse.wav"
        with wave.open(str(source), "wb") as wav:
            wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(compose().tobytes())
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(source),
                        "-map_metadata", "-1", "-c:a", "libvorbis", "-q:a", "4",
                        "-metadata", "title=Containment Pulse",
                        "-metadata", "artist=RE Forge Demo original synthesis",
                        "-metadata", "comment=Original score and synthesis; no samples; audit 20261004",
                        str(args.output)], check=True, timeout=60)
    print(f"Wrote {args.output}: {SECONDS}s, mono Vorbis, {RATE}Hz")


if __name__ == "__main__":
    main()
