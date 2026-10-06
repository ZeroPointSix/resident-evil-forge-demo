#!/usr/bin/env python3
"""Verify the original music resource, registration, decoded signal and release JAR."""

from array import array
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

ASSETS = Path("src/main/resources/assets/re_demo")
AUDIO = Path("sounds/music/containment_pulse.ogg")
REGISTRY = Path("src/main/java/com/zeropointsix/redemo/registry/ModSounds.java")
SUBTITLE = "subtitles.re_demo.encounter_theme"


def validate(root: Path, jar: Path | None = None) -> dict:
    assets = root / ASSETS
    path = assets / AUDIO
    raw = path.read_bytes()
    if not raw.startswith(b"OggS") or b"\x01vorbis" not in raw[:128]:
        raise ValueError("Music must be an actual Ogg Vorbis resource")
    sounds = json.loads((assets / "sounds.json").read_text(encoding="utf-8"))
    event = sounds.get("encounter_theme", {})
    expected = {"name": "re_demo:music/containment_pulse", "stream": True}
    if event.get("sounds") != [expected] or event.get("subtitle") != SUBTITLE:
        raise ValueError("Original music must stream the local resource, not a vanilla forwarded event")
    for locale in ("en_us", "zh_cn"):
        if not json.loads((assets / f"lang/{locale}.json").read_text(encoding="utf-8")).get(SUBTITLE):
            raise ValueError(f"Missing original music subtitle: {locale}")
    if 'ENCOUNTER_THEME = sound("encounter_theme")' not in (root / REGISTRY).read_text():
        raise ValueError("Original music is missing from the deferred sound registration")
    info = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                           str(path)], check=True, capture_output=True, text=True, timeout=30)
    data = json.loads(info.stdout)
    streams = data.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "vorbis":
        raise ValueError("Exactly one Vorbis audio stream is required")
    stream = streams[0]
    if stream.get("channels") != 1 or stream.get("sample_rate") != "44100":
        raise ValueError("Music must be mono at 44100 Hz")
    duration = float(data["format"]["duration"])
    if not 23.9 <= duration <= 24.1:
        raise ValueError(f"Unexpected original cue duration: {duration}")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-f", "f32le", "-"],
                             check=True, capture_output=True, timeout=30)
    samples = array("f")
    samples.frombytes(decoded.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) < 23.8 * 44100 or not all(math.isfinite(v) for v in samples):
        raise ValueError("Incomplete or invalid decoded music")
    peak = max(abs(v) for v in samples)
    rms = math.sqrt(sum(v * v for v in samples) / len(samples))
    if rms < 0.02 or not 0.1 < peak < 0.99:
        raise ValueError(f"Silent or clipped music: RMS={rms}, peak={peak}")
    if jar is not None:
        with zipfile.ZipFile(jar) as archive:
            for relative in (AUDIO, Path("sounds.json"), Path("lang/en_us.json"), Path("lang/zh_cn.json")):
                if archive.read(f"assets/re_demo/{relative.as_posix()}") != (assets / relative).read_bytes():
                    raise ValueError(f"Packaged music resource differs from source: {relative}")
            registry_class = "com/zeropointsix/redemo/registry/ModSounds.class"
            if b"encounter_theme" not in archive.read(registry_class):
                raise ValueError("Packaged sound registry lacks the original event")
    return {"passed": True, "event": "re_demo:encounter_theme", "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "seconds": duration,
            "channels": 1, "sample_rate": 44100, "codec": "vorbis",
            "rms": round(rms, 6), "peak": round(peak, 6), "jar_verified": jar is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--jar", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        report = validate(args.root, args.jar)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        report = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
