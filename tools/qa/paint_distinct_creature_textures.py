#!/usr/bin/env python3
"""Paint distinct 64x64 RGBA creature palettes from runtime UV boxes.

Does not change geometry, bones, or animation tracks. Each creature keeps the
approved UV layout; only texel colors change so Licker / Tyrant / G1 read as
different models in the client.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import re
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "src/main/resources/assets/re_demo/geo"
RUNTIME = ROOT / "src/main/resources/assets/re_demo/textures/entity"
APPROVED = ROOT / "art/blockbench/20261004"
ART = ROOT / "art"
SIZE = 64

# Accent colors keyed by UV origin. Shared atlas tiles stay one material, but
# each creature uses a different material set so hats/tongues/eyes still read.
PALETTES = {
    "licker": {
        "default": (168, 42, 48, 255),
        (2, 2): (232, 214, 176, 255),       # claws / bone
        (6, 6): (232, 214, 176, 255),
        (34, 2): (214, 96, 108, 255),       # skull / hunched flesh
        (38, 6): (214, 96, 108, 255),
        (42, 2): (176, 48, 58, 255),        # limbs / jaw
        (46, 6): (176, 48, 58, 255),
        (42, 10): (255, 72, 168, 255),      # tongue
        (46, 14): (255, 72, 168, 255),
        (18, 10): (72, 16, 24, 255),        # jaw cavity
        (22, 14): (72, 16, 24, 255),
        (50, 2): (255, 150, 176, 255),      # exposed brain / neck
        (54, 6): (255, 150, 176, 255),
    },
    "tyrant": {
        "default": (28, 40, 48, 255),
        (10, 2): (18, 28, 34, 255),         # coat / hat crown
        (14, 6): (18, 28, 34, 255),
        (18, 2): (32, 52, 60, 255),         # coat panels / collar
        (22, 6): (32, 52, 60, 255),
        (26, 2): (186, 176, 158, 255),      # skin / fists
        (30, 6): (186, 176, 158, 255),
        (26, 10): (16, 16, 18, 255),        # boots / hat brim
        (30, 14): (16, 16, 18, 255),
        (18, 10): (48, 36, 32, 255),        # eye sockets / mouth
        (22, 14): (48, 36, 32, 255),
        (10, 10): (198, 162, 56, 255),      # buckle / hat clip
        (14, 14): (198, 162, 56, 255),
    },
    "g1_birkin": {
        "default": (206, 164, 104, 255),
        (2, 2): (245, 238, 214, 255),       # open eye sclera / bone
        (6, 6): (245, 238, 214, 255),
        (2, 10): (176, 36, 40, 255),        # mutation flesh
        (6, 14): (176, 36, 40, 255),
        (2, 18): (196, 148, 92, 255),       # legs
        (6, 22): (196, 148, 92, 255),
        (18, 10): (24, 16, 12, 255),        # pupil / eye slots
        (22, 14): (24, 16, 12, 255),
        (26, 2): (214, 176, 120, 255),      # head / normal arm
        (30, 6): (214, 176, 120, 255),
        (26, 10): (32, 24, 20, 255),        # boots
        (30, 14): (32, 24, 20, 255),
        (34, 10): (240, 176, 28, 255),      # iris
        (38, 14): (240, 176, 28, 255),
        (50, 2): (148, 40, 44, 255),        # socket / elbow
        (54, 6): (148, 40, 44, 255),
        (50, 10): (92, 56, 44, 255),        # ragged coat
        (54, 14): (92, 56, 44, 255),
        (58, 2): (188, 48, 42, 255),        # giant fingers / closed eye
        (62, 6): (188, 48, 42, 255),
        (58, 10): (56, 36, 28, 255),        # hair / lapel
        (62, 14): (56, 36, 28, 255),
    },
}


def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)


def write_rgba_png(path: Path, pixels: list[tuple[int, int, int, int]]) -> None:
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        for x in range(SIZE):
            raw.extend(pixels[y * SIZE + x])
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def fill_uv(pixels: list[tuple[int, int, int, int]], origin, size, color) -> None:
    x, y = origin
    w, h = size
    x0, x1 = sorted((x, x + w))
    y0, y1 = sorted((y, y + h))
    x0 = max(0, int(math.floor(x0)))
    y0 = max(0, int(math.floor(y0)))
    x1 = min(SIZE, int(math.ceil(x1)))
    y1 = min(SIZE, int(math.ceil(y1)))
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            pixels[yy * SIZE + xx] = color


def paint(creature: str) -> bytes:
    geo = json.loads((GEO / f"{creature}.geo.json").read_text(encoding="utf-8"))
    palette = PALETTES[creature]
    pixels = [(0, 0, 0, 0)] * (SIZE * SIZE)
    for bone in geo["minecraft:geometry"][0]["bones"]:
        for cube in bone.get("cubes") or []:
            uv = cube.get("uv")
            if not isinstance(uv, dict):
                continue
            for face in uv.values():
                origin = tuple(face["uv"])
                color = palette.get(origin, palette["default"])
                fill_uv(pixels, face["uv"], face.get("uv_size", [0, 0]), color)
    path = RUNTIME / f"{creature}.png"
    write_rgba_png(path, pixels)
    data = path.read_bytes()
    (APPROVED / f"{creature}_palette.png").write_bytes(data)
    encoded = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    for project in (ART / f"{creature}.bbmodel", APPROVED / f"{creature}.bbmodel"):
        text = project.read_text(encoding="utf-8")
        updated, count = re.subn(r'"source": "data:image/png;base64,[^"]+"', f'"source": "{encoded}"', text, count=1)
        if count != 1:
            raise SystemExit(f"{project}: expected one embedded PNG source, found {count}")
        project.write_text(updated, encoding="utf-8")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_manifests(digests: dict[str, str]) -> None:
    manifest_path = ART / "creature_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for creature, digest in digests.items():
        files = manifest["creatures"][creature]["files"]
        files[f"src/main/resources/assets/re_demo/textures/entity/{creature}.png"] = digest
        files[f"art/{creature}.bbmodel"] = sha256(ART / f"{creature}.bbmodel")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    report_path = APPROVED / "blockbench_validation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for creature, digest in digests.items():
        report["file_sha256"][f"{creature}_palette.png"] = digest
        report["file_sha256"][f"{creature}.bbmodel"] = sha256(APPROVED / f"{creature}.bbmodel")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    digests = {}
    for creature in ("licker", "tyrant", "g1_birkin"):
        data = paint(creature)
        digests[creature] = hashlib.sha256(data).hexdigest()
        print(f"{creature}: {len(data)} bytes sha256={digests[creature]}")
    if len(set(digests.values())) != 3:
        raise SystemExit(f"textures are still identical: {digests}")
    refresh_manifests(digests)
    print("updated art/creature_manifest.json and blockbench_validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
