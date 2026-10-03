"""Generate the deterministic, empty 16x8x16 Minecraft GameTest structure."""
import gzip
import struct
from pathlib import Path


def utf8(value):
    data = value.encode("utf-8")
    return struct.pack(">H", len(data)) + data


def tag(kind, name, payload):
    return bytes([kind]) + utf8(name) + payload


def generate():
    dimensions = tag(9, "size", bytes([3]) + struct.pack(">iiii", 3, 16, 8, 16))
    palette = tag(9, "palette", bytes([10]) + struct.pack(">i", 1)
                  + tag(8, "Name", utf8("minecraft:air")) + b"\0")
    empty = b"".join(tag(9, key, bytes([10]) + struct.pack(">i", 0)) for key in ("blocks", "entities"))
    root = tag(10, "", tag(3, "DataVersion", struct.pack(">i", 3465)) + dimensions + palette + empty + b"\0")
    destination = Path(__file__).resolve().parents[1] / "src/main/resources/data/re_demo/structures/empty.nbt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(gzip.compress(root, mtime=0))
    print(f"Generated {destination.name}: {destination.stat().st_size} bytes")


if __name__ == "__main__":
    generate()
