"""Generate an open 128x128 arena loaded directly by the GameTest structure API."""

import gzip
from pathlib import Path
import struct

SIZE = 128

def string(value):
    data = value.encode("utf-8")
    return struct.pack(">H", len(data)) + data


def tag(kind, name, payload):
    return bytes([kind]) + string(name) + payload


def integer(value):
    return struct.pack(">i", value)


def list_tag(name, kind, values):
    return tag(9, name, bytes([kind]) + integer(len(values)) + b"".join(values))


def generate():
    palette = tag(8, "Name", string("minecraft:stone")) + b"\x00"
    blocks = [
        list_tag("pos", 3, [integer(x), integer(0), integer(z)])
        + tag(3, "state", integer(0)) + b"\x00"
        for x in range(SIZE) for z in range(SIZE)
    ]
    body = tag(3, "DataVersion", integer(3465))
    body += list_tag("size", 3, [integer(SIZE), integer(12), integer(SIZE)])
    body += list_tag("palette", 10, [palette])
    body += list_tag("blocks", 10, blocks)
    body += list_tag("entities", 10, []) + b"\x00"
    return gzip.compress(tag(10, "", body), mtime=0)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    destination = root / "src/main/resources/data/re_demo/structures/combat_arena.nbt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(generate())
    print(destination)
