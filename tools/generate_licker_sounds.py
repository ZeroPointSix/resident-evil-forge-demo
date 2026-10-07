"""Original procedural creature Foley. No samples or franchise audio are used."""

import array
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys


RATE = 22050
DURATIONS = {"hiss": 0.75, "hurt": 0.42, "death": 1.2, "tongue": 0.32}


def synthesize(name, duration):
    rng = random.Random(601 + list(DURATIONS).index(name))
    samples = array.array("h")
    phase = 0.0
    filtered = 0.0
    for index in range(round(RATE * duration)):
        t = index / RATE
        fraction = t / duration
        noise = rng.uniform(-1, 1)
        filtered = 0.82 * filtered + 0.18 * noise
        if name == "tongue":
            frequency = 480 * (1 - fraction) + 75
            envelope = math.sin(math.pi * fraction) ** 0.5 * math.exp(-4 * fraction)
            tone = 0.35 * math.sin(phase) + 0.7 * (noise - filtered)
        else:
            base = {"hiss": 95, "hurt": 210, "death": 140}[name]
            frequency = base * (1.2 - 0.8 * fraction) * (1 + 0.08 * math.sin(2 * math.pi * 37 * t))
            envelope = min(1, t / 0.018) * (1 - fraction) ** 0.7
            breath = 0.7 + 0.3 * math.sin(2 * math.pi * 22 * t)
            tone = (0.45 * math.sin(phase) + 0.22 * math.sin(phase * 2.07) + 1.8 * filtered) * breath
            if name == "hiss":
                tone = 0.2 * tone + 0.7 * (noise - filtered)
        phase += 2 * math.pi * frequency / RATE
        samples.append(round(math.tanh(tone * 1.5) * envelope * 21000))
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "src/main/resources/assets/re_demo/sounds/licker"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"origin": "Original deterministic synthesis; no external samples", "license": "MIT", "generator": "tools/generate_licker_sounds.py", "files": {}}
    for name, duration in DURATIONS.items():
        destination = output / (name + ".ogg")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0", "-c:a", "libvorbis", "-q:a", "4", "-map_metadata", "-1", str(destination)], input=synthesize(name, duration), check=True)
        manifest["files"][destination.name] = {"seconds": duration, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    (output / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
