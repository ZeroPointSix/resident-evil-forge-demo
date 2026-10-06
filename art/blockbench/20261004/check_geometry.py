"""Independent structural checks for GeckoLib 4 cube-only review assets."""
import hashlib
import json
import math
from pathlib import Path
import sys
from PIL import Image

root = Path(sys.argv[1])
report = {"models": {}, "runtime_tested": False}
for name in ("tyrant", "g1_birkin", "licker"):
    path = root/(name+".geo.json")
    data = json.loads(path.read_text())
    assert data["format_version"] == "1.12.0"
    assert len(data["minecraft:geometry"]) == 1
    model = data["minecraft:geometry"][0]
    bones = model["bones"]
    names = {b["name"] for b in bones}
    assert len(names) == len(bones)
    parents = {b["name"]: b.get("parent") for b in bones}
    assert sum(parent is None for parent in parents.values()) == 1
    for name_ in names:
        seen = set()
        while name_:
            assert name_ not in seen and name_ in names
            seen.add(name_)
            name_ = parents[name_]
    width = model["description"]["texture_width"]
    height = model["description"]["texture_height"]
    assert Image.open(root/(name+"_palette.png")).size == (width, height)
    cubes = [c for b in bones for c in b.get("cubes", [])]
    for bone in bones:
        assert "poly_mesh" not in bone and "texture_meshes" not in bone
    for cube in cubes:
        assert all(len(cube.get(key, [0, 0, 0])) == 3 for key in ("origin", "size", "pivot", "rotation"))
        assert all(math.isfinite(v) for key in ("origin", "size", "pivot", "rotation") for v in cube.get(key, []))
        assert all(v > 0 for v in cube["size"])
        assert set(cube["uv"]) == {"north", "south", "west", "east", "up", "down"}
        for face in cube["uv"].values():
            assert "uv_rotation" not in face
            for axis, limit in enumerate((width, height)):
                u, size = face["uv"][axis], face["uv_size"][axis]
                assert 0 <= u <= limit and 0 <= u+size <= limit and abs(size) > 0
    report["models"][name] = {"cubes": len(cubes), "bones": len(bones), "logical_vertices": len(cubes)*8,
                              "positive_volume": True, "acyclic_hierarchy": True, "all_uvs_in_bounds": True,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
(root/"geometry_validation.json").write_text(json.dumps(report, indent=2)+"\n")
print("GEOMETRY_CHECKS_PASSED", json.dumps(report))
