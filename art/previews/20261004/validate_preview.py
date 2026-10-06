"""Narrow, repeatable checks for the preview deliverable, not game compatibility."""

import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageStat


root = Path(sys.argv[1])
stats = json.loads((root/"model_stats.json").read_text())
assert stats["tool"].startswith("Blender 4.")
assert stats["source_sha256"] == hashlib.sha256((Path(__file__).parent/"build_blockouts.py").read_bytes()).hexdigest()
assert stats["source_commit"] == os.environ.get("GITHUB_SHA", "local")
report = {"checks": [], "files": {}}
for name in ("tyrant", "g1_birkin", "licker"):
    item = stats["models"][name]
    assert 50 < item["polygons"] < 5000, item
    assert item["all_parts_closed_manifold"]
    assert min(item["dimensions_xyz_m"]) > .50
    for view in ("front", "side", "back", "three_quarter", "turnaround"):
        path = root/f"{name}_{view}.png"
        with Image.open(path) as image:
            image.load()
            assert min(image.size) >= 1000
            assert max(ImageStat.Stat(image).stddev) > 10, path
    obj = root/f"{name}.obj"
    lines = obj.read_text().splitlines()
    assert sum(line.startswith("f ") for line in lines) == item["polygons"]
    assert (root/f"{name}.mtl").stat().st_size > 100
    report["checks"].append(name+": closed solid parts, nonblank views, OBJ face counts match")
assert stats["models"]["tyrant"]["dimensions_xyz_m"][2] > stats["models"]["g1_birkin"]["dimensions_xyz_m"][2]
assert stats["models"]["g1_birkin"]["dimensions_xyz_m"][2] > 2*stats["models"]["licker"]["dimensions_xyz_m"][2]
assert stats["lineup"]["same_world_scale"]
assert stats["lineup"]["camera_bounds_verified"]
assert all(scale == [1, 1, 1] for scale in stats["lineup"]["model_scales"].values())
for filename in ("review_overview.png", "lineup.png", "lineup_review.png"):
    with Image.open(root/filename) as image:
        image.load()
        assert min(image.size) >= 1000
        assert max(ImageStat.Stat(image).stddev) > 10
interchange = json.loads((root/"interchange_validation.json").read_text())
assert interchange["blend_reopened"]
assert all(interchange["obj_reimported"].values())
assert (root/"monster_blockouts.blend").stat().st_size > 10000
for path in sorted(root.iterdir()):
    if path.is_file() and path.name != "validation.json":
        report["files"][path.name] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
report["checks"].append("lineup: same unit scale, orthographic projection, all mesh vertices within frame")
report["game_runtime_tested"] = False
report["interchange"] = interchange
report["approval_status"] = "awaiting user visual review"
(root/"validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(report, ensure_ascii=False))
