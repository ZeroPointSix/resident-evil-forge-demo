#!/usr/bin/env python3
"""Validate the three-creature resource contract, not gameplay or visual quality."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import struct
import sys
import zipfile
import zlib
from pathlib import Path
from typing import Any


MOD_ID = "re_demo"
COMMON = ("idle", "walk", "hurt", "death")
CONTRACTS = {
    "licker": {
        "attacks": {"claw": 0.45, "leap": 0.60, "tongue": 0.55, "ambush": 0.60},
        "bones": (),
    },
    "tyrant": {
        "attacks": {"punch": 0.80, "shove": 0.50, "charge": 1.00, "break": 0.70, "rage": 0.0},
        "bones": ("coat_intact", "coat_torn"),
    },
    "g1_birkin": {
        "attacks": {"slam": 0.90, "sweep": 1.00, "grab": 0.75, "rage": 0.0},
        "bones": ("eye_open", "eye_closed"),
    },
}
MAX_FILE_BYTES = 32 * 1024 * 1024


class InvalidAsset(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidAsset(message)


def number(value: Any) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def vector(value: Any, length: int = 3) -> bool:
    return isinstance(value, list) and len(value) == length and all(number(v) for v in value)


def load_json(data: bytes) -> dict:
    require(len(data) <= MAX_FILE_BYTES, "JSON exceeds size limit")

    def unique(pairs: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        result = json.loads(data, object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InvalidAsset(f"invalid JSON: {exc}") from exc
    require(isinstance(result, dict), "JSON root must be an object")
    return result


def png_size(data: bytes) -> tuple[int, int]:
    require(len(data) <= MAX_FILE_BYTES, "PNG exceeds size limit")
    require(data.startswith(b"\x89PNG\r\n\x1a\n"), "invalid PNG signature")
    offset = 8
    chunks = []
    compressed = bytearray()
    header = None
    ended = False
    palette = None
    while offset < len(data):
        require(offset + 12 <= len(data), "truncated PNG chunk")
        size = struct.unpack_from(">I", data, offset)[0]
        require(offset + 12 + size <= len(data), "truncated PNG payload")
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        require((binascii.crc32(kind + payload) & 0xFFFFFFFF) == crc, "PNG CRC mismatch")
        chunks.append(kind)
        if kind == b"IHDR":
            require(header is None and len(chunks) == 1 and size == 13, "invalid PNG IHDR")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"PLTE":
            require(palette is None and b"IDAT" not in chunks, "invalid PNG palette order")
            require(3 <= size <= 768 and size % 3 == 0, "invalid PNG palette length")
            palette = size // 3
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            require(size == 0, "invalid PNG IEND")
            ended = True
            offset += 12
            break
        offset += size + 12
    require(ended and offset == len(data) and header is not None, "missing PNG end or trailing data")
    width, height, depth, color, compression, filtering, interlace = header
    require(0 < width <= 4096 and 0 < height <= 4096, "invalid PNG dimensions")
    require(compression == 0 and filtering == 0 and interlace in (0, 1), "unsupported PNG header")
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    require(color in depths and depth in depths[color], "invalid PNG color/bit-depth")
    if color == 3:
        require(palette is not None and palette <= 2**depth, "invalid or missing indexed PNG palette")
    elif color in (0, 4):
        require(palette is None, "grayscale PNG must not have a palette")
    require(bool(compressed), "PNG has no pixel data")
    try:
        decoder = zlib.decompressobj()
        pixels = decoder.decompress(bytes(compressed), MAX_FILE_BYTES + 1)
        require(len(pixels) <= MAX_FILE_BYTES and not decoder.unconsumed_tail, "PNG decoded data exceeds limit")
        require(decoder.eof and not decoder.unused_data, "incomplete PNG deflate stream")
    except zlib.error as exc:
        raise InvalidAsset(f"invalid PNG pixel data: {exc}") from exc
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    passes = [(0, 0, 1, 1)] if interlace == 0 else [
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
    ]
    position = 0
    for x, y, dx, dy in passes:
        columns = max(0, (width - x + dx - 1) // dx)
        rows = max(0, (height - y + dy - 1) // dy)
        if not columns or not rows:
            continue
        row_bytes = (columns * channels * depth + 7) // 8
        require(position + rows * (row_bytes + 1) <= len(pixels), "truncated PNG scanlines")
        for row in range(rows):
            require(pixels[position + row * (row_bytes + 1)] <= 4, "invalid PNG row filter")
        position += rows * (row_bytes + 1)
    require(position == len(pixels), "PNG scanline length mismatch")
    return width, height


def validate_uv(uv: Any, texture_size: tuple[int, int]) -> None:
    if vector(uv, 2):
        require(all(0 <= v < size for v, size in zip(uv, texture_size)), "box UV origin outside texture")
        return
    require(isinstance(uv, dict) and bool(uv), "missing/invalid UV")
    require(set(uv).issubset({"north", "south", "east", "west", "up", "down"}), "unknown UV face")
    for face in uv.values():
        require(isinstance(face, dict) and vector(face.get("uv"), 2), "invalid face UV")
        size = face.get("uv_size", [0, 0])
        require(vector(size, 2), "invalid face UV size")
        for start, extent, limit in zip(face["uv"], size, texture_size):
            require(0 <= start <= limit and 0 <= start + extent <= limit, "face UV outside texture")


def validate_geometry(model: dict, texture_size: tuple[int, int], creature: str) -> set[str]:
    geometries = model.get("minecraft:geometry")
    require(isinstance(geometries, list) and len(geometries) == 1, "expected one GeckoLib geometry")
    geometry = geometries[0]
    require(isinstance(geometry, dict), "geometry must be an object")
    description = geometry.get("description", {})
    require(isinstance(description, dict), "geometry description must be an object")
    require(isinstance(description.get("identifier"), str), "missing geometry identifier")
    require((description.get("texture_width"), description.get("texture_height")) == texture_size,
            "geometry texture dimensions differ from PNG")
    bones = geometry.get("bones", [])
    require(isinstance(bones, list) and bones, "geometry has no bones")
    names = set()
    parents = {}
    cube_count = 0
    for bone in bones:
        require(isinstance(bone, dict), "bone must be an object")
        name = bone.get("name")
        require(isinstance(name, str) and name and name not in names, "missing or duplicate bone name")
        names.add(name)
        parent = bone.get("parent")
        require(parent is None or isinstance(parent, str), f"{name}: parent must be a string")
        parents[name] = parent
        for field in ("pivot", "rotation"):
            require(field not in bone or vector(bone[field]), f"{name}: invalid {field}")
        cubes = bone.get("cubes", [])
        require(isinstance(cubes, list), f"{name}: cubes must be a list")
        for cube in cubes:
            require(isinstance(cube, dict), f"{name}: cube must be an object")
            require(vector(cube.get("origin")) and vector(cube.get("size")), f"{name}: invalid cube dimensions")
            require(all(v >= 0 for v in cube["size"]) and sum(v > 0 for v in cube["size"]) >= 2,
                    f"{name}: degenerate cube")
            uv = cube.get("uv")
            validate_uv(uv, texture_size)
            for field in ("pivot", "rotation"):
                require(field not in cube or vector(cube[field]), f"{name}: invalid cube {field}")
            cube_count += 1
    for name, parent in parents.items():
        require(parent is None or parent in names, f"{name}: unknown parent {parent}")
        visited = {name}
        while parent is not None:
            require(parent not in visited, f"{name}: cyclic bone hierarchy")
            visited.add(parent)
            parent = parents.get(parent)
    require(cube_count >= 20, f"expected at least 20 designed cubes, found {cube_count}")
    require(set(CONTRACTS[creature]["bones"]).issubset(names), f"{creature}: missing visual-state bones")
    return names


def transform(value: Any) -> bool:
    if isinstance(value, list):
        return len(value) == 3 and all(number(v) or isinstance(v, str) and bool(v.strip()) for v in value)
    if isinstance(value, dict):
        samples = [value[k] for k in ("pre", "post", "vector") if k in value]
        return bool(samples) and all(transform(sample) for sample in samples)
    return False


def dynamic_track(track: Any, length: float) -> bool:
    def samples(value: Any) -> list[list]:
        if isinstance(value, list):
            return [value]
        return [sample for key in ("pre", "post", "vector") if key in value for sample in samples(value[key])]

    def dynamic_expression(value: list) -> bool:
        return any(isinstance(v, str) and any(s in v for s in ("query.", "math.", "q.")) for v in value)

    if isinstance(track, list):
        require(transform(track), "invalid animation vector")
        return dynamic_expression(track)
    require(isinstance(track, dict) and track, "empty animation track")
    values = []
    for timestamp, value in track.items():
        try:
            time = float(timestamp)
        except (TypeError, ValueError) as exc:
            raise InvalidAsset(f"invalid keyframe time: {timestamp}") from exc
        require(math.isfinite(time) and 0 <= time <= length + 0.0001, "keyframe outside animation duration")
        require(transform(value), "invalid animation keyframe")
        values.extend(samples(value))
    return any(dynamic_expression(value) for value in values) or any(value != values[0] for value in values[1:])


def validate_animations(data: dict, bones: set[str], creature: str) -> None:
    animations = data.get("animations")
    require(isinstance(animations, dict), "missing animations object")
    attacks = CONTRACTS[creature]["attacks"]
    for action in (*COMMON, *attacks):
        name = f"animation.{creature}.{action}"
        animation = animations.get(name)
        require(isinstance(animation, dict), f"missing animation: {name}")
        length = animation.get("animation_length")
        require(number(length) and length > 0, f"{name}: invalid duration")
        if action in attacks:
            require(length >= attacks[action], f"{name}: ends before contracted impact/start time")
        if action in ("idle", "walk"):
            require(animation.get("loop") is True, f"{name}: locomotion must loop")
        else:
            require(animation.get("loop", False) in (False, "hold_on_last_frame"), f"{name}: action must not repeat")
        tracks = animation.get("bones", {})
        require(isinstance(tracks, dict) and tracks, f"{name}: no animated bones")
        changed = False
        for bone, channels in tracks.items():
            require(bone in bones, f"{name}: unknown bone {bone}")
            require(isinstance(channels, dict), f"{name}: channels must be an object")
            for channel, track in channels.items():
                require(channel in ("rotation", "position", "scale"), f"{name}: invalid transform channel")
                changed = dynamic_track(track, length) or changed
        require(changed, f"{name}: animation has no changing transforms")


def validate_blockbench(data: dict, names: set[str], texture_size: tuple[int, int]) -> None:
    meta = data.get("meta")
    require(isinstance(meta, dict) and isinstance(meta.get("format_version"), str), "missing Blockbench metadata")
    elements = data.get("elements")
    require(isinstance(elements, list) and len(elements) >= 20, "Blockbench source is missing model cubes")
    ids = []
    for element in elements:
        require(isinstance(element, dict), "invalid Blockbench element")
        require(isinstance(element.get("uuid"), str), "Blockbench element is missing uuid")
        require(vector(element.get("from")) and vector(element.get("to")), "invalid Blockbench cube coordinates")
        require(all(b >= a for a, b in zip(element["from"], element["to"])), "inverted Blockbench cube")
        ids.append(element["uuid"])
    require(len(set(ids)) == len(ids), "duplicate Blockbench cube uuid")
    groups = set()
    references = []

    def visit(nodes: Any) -> None:
        require(isinstance(nodes, list), "Blockbench outliner must be a list")
        for node in nodes:
            if isinstance(node, str):
                references.append(node)
            else:
                require(isinstance(node, dict) and isinstance(node.get("name"), str), "invalid Blockbench group")
                groups.add(node["name"])
                visit(node.get("children", []))

    visit(data.get("outliner"))
    require(set(references) == set(ids) and len(references) == len(ids), "Blockbench outliner must reference every cube once")
    require(names.issubset(groups), "Blockbench source is missing runtime bones")
    textures = data.get("textures", [])
    require(isinstance(textures, list) and textures, "Blockbench source has no textures")
    embedded = False
    for texture in textures:
        require(isinstance(texture, dict), "invalid Blockbench texture")
        source = texture.get("source", "")
        if isinstance(source, str) and source.startswith("data:image/png;base64,"):
            try:
                pixels = base64.b64decode(source.split(",", 1)[1], validate=True)
            except (ValueError, binascii.Error) as exc:
                raise InvalidAsset("invalid embedded Blockbench PNG") from exc
            require(png_size(pixels) == texture_size, "Blockbench texture size differs from runtime texture")
            embedded = True
    require(embedded, "Blockbench source must embed a portable PNG texture")


def validate(root: Path, jar: Path | None = None) -> dict:
    report = {
        "kind": "static-resource-contract", "gameplay_verified": False, "creatures": {}, "errors": [],
        "jar_resource_check": {"requested": jar is not None, "passed": False, "matched_resources": 0},
    }
    packed = None
    if jar:
        try:
            packed = zipfile.ZipFile(jar)
            size = packed.fp.seek(0, 2)
            packed.fp.seek(0)
            report["jar_resource_check"].update({
                "name": jar.name,
                "sha256": hashlib.file_digest(packed.fp, "sha256").hexdigest(),
                "bytes": size,
            })
            require(len(packed.namelist()) == len(set(packed.namelist())), "JAR contains duplicate entries")
            require("META-INF/mods.toml" in packed.namelist(), "JAR has no Forge mods.toml")
        except (OSError, zipfile.BadZipFile, InvalidAsset) as exc:
            if packed:
                packed.close()
            report["errors"].append(f"JAR: {exc}")
            return report
    try:
        for creature in CONTRACTS:
            try:
                relative = {
                    "geo": f"assets/{MOD_ID}/geo/{creature}.geo.json",
                    "animation": f"assets/{MOD_ID}/animations/{creature}.animation.json",
                    "texture": f"assets/{MOD_ID}/textures/entity/{creature}.png",
                }
                content = {}
                for key, path in relative.items():
                    file = root / "src/main/resources" / path
                    require(file.stat().st_size <= MAX_FILE_BYTES, f"oversized resource: {path}")
                    content[key] = file.read_bytes()
                    if packed:
                        info = packed.getinfo(path)
                        require(info.file_size <= MAX_FILE_BYTES, f"oversized JAR resource: {path}")
                        require(packed.read(path) == content[key], f"JAR resource differs from source: {path}")
                        report["jar_resource_check"]["matched_resources"] += 1
                size = png_size(content["texture"])
                names = validate_geometry(load_json(content["geo"]), size, creature)
                validate_animations(load_json(content["animation"]), names, creature)
                source = root / "art" / f"{creature}.bbmodel"
                require(source.stat().st_size <= MAX_FILE_BYTES, "oversized Blockbench source")
                validate_blockbench(load_json(source.read_bytes()), names, size)
                report["creatures"][creature] = {"passed": True, "bones": len(names), "texture": list(size)}
            except (OSError, KeyError, InvalidAsset, zipfile.BadZipFile, RuntimeError, zlib.error, RecursionError) as exc:
                report["creatures"][creature] = {"passed": False}
                report["errors"].append(f"{creature}: {exc}")
    finally:
        if packed:
            packed.close()
    report["jar_resource_check"]["passed"] = jar is not None and not report["errors"]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--jar", type=Path, help="Also check exact resource bytes inside the built Forge JAR")
    parser.add_argument("--report", type=Path, help="Write machine-readable static verification results")
    args = parser.parse_args(argv)
    report = validate(args.root.resolve(), args.jar)
    output = json.dumps(report, indent=2, ensure_ascii=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
