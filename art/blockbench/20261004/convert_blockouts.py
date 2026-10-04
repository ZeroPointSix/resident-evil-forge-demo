"""Convert the approved Blender mesh parts to editable cuboids, without redesigning.

Run in Blender 4. The final BBModel and GEO are compiled by real Blockbench in
validate_blockbench.cjs, not by this intermediate geometry extractor.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sys

import bpy
from mathutils import Matrix, Vector


SCALE = 16.0
SOURCE_COMMIT = "98585964b9c1e96884b6b11ca8c5c9640b5a1cfb"
AXIS = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))
NAMES = ("tyrant", "g1_birkin", "licker")


def vec(value):
    return [round(float(v), 6) for v in value]


def bounds(points):
    return [[min(p[a] for p in points) for a in range(3)],
            [max(p[a] for p in points) for a in range(3)]]


def clipped_section(z0, z1, center, width, depth):
    """Three solid bands approximate the original clipped-rectangle section."""
    x, y = center
    corner = min(width, depth) * .15
    return [
        ([x-width/2, y-depth/2+corner, z0],
         [x+width/2, y+depth/2-corner, z1]),
        ([x-(width-corner)/2, y-depth/2, z0],
         [x+(width-corner)/2, y-depth/2+corner, z1]),
        ([x-(width-corner)/2, y+depth/2-corner, z0],
         [x+(width-corner)/2, y+depth/2, z1]),
    ]


def mesh_boxes(obj):
    points = [list(v.co) for v in obj.data.vertices]
    # Original lofts have octagonal end caps; beveled boxes do not.
    if not any(len(p.vertices) == 8 for p in obj.data.polygons):
        return [bounds(points)], "oriented_box"
    assert len(points) % 8 == 0, obj.name
    rings = []
    for offset in range(0, len(points), 8):
        lo, hi = bounds(points[offset:offset+8])
        assert abs(hi[2]-lo[2]) < .00001, obj.name
        rings.append((lo[2], hi[0]-lo[0], hi[1]-lo[1],
                      (lo[0]+hi[0])/2, (lo[1]+hi[1])/2))
    boxes = []
    for a, b in zip(rings, rings[1:]):
        assert b[0] > a[0], obj.name
        variation = max(abs(b[i]-a[i]) for i in range(1, 5))
        slices = max(1, min(8, math.ceil(variation/.065)))
        for index in range(slices):
            t = (index+.5)/slices
            mid = [x+(y-x)*t for x, y in zip(a, b)]
            z0 = a[0]+(b[0]-a[0])*index/slices
            z1 = a[0]+(b[0]-a[0])*(index+1)/slices
            boxes.extend(clipped_section(z0, z1, mid[3:5], mid[1], mid[2]))
    return boxes, "stepped_loft"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index("--")+1:]
    args = parser.parse_args(argv)
    source, output = Path(args.source), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    assert bpy.app.version[0] == 4
    palette = sorted({o.data.materials[0].name for name in NAMES
                      for o in bpy.data.collections[name].objects if o.type == "MESH"})
    materials = {name: vec(bpy.data.materials[name].diffuse_color[:3]) for name in palette}
    result = {"source_commit": SOURCE_COMMIT,
              "source_blend_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "blender_version": bpy.app.version_string,
              "units": "16 model units = 1 Blender metre",
              "axis": "Blender (x,y,z) -> Blockbench (x,z,-y)",
              "approximation": "Bevels become cuboids; clipped loft profiles become solid stepped cuboids. No silhouette redesign.",
              "materials_linear_rgb": materials, "models": {}}
    for name in NAMES:
        objects = sorted([o for o in bpy.data.collections[name].objects if o.type == "MESH"], key=lambda o:o.name)
        parts, cubes, source_points, converted_points = [], [], [], []
        for obj in objects:
            label = re.sub(r"\.\d{3}$", "", obj.name)
            matrix = obj.matrix_local.copy()
            translation = AXIS @ matrix.translation * SCALE
            rotation_matrix = AXIS @ matrix.to_3x3() @ AXIS.transposed()
            # Blockbench uses THREE Euler ZYX, equivalent to Blender's XYZ.
            rotation = vec(math.degrees(x) for x in rotation_matrix.to_euler("XYZ"))
            local_boxes, method = mesh_boxes(obj)
            expected = []
            for i, (lo, hi) in enumerate(local_boxes):
                local_corners = [Vector(c) for c in itertools.product(*zip(lo, hi))]
                corners = [AXIS @ (matrix @ c) * SCALE for c in local_corners]
                pre = [AXIS @ c * SCALE + translation for c in local_corners]
                pre_lo, pre_hi = bounds(pre)
                cube = {"name": f"{label}_{i:02d}", "part": label,
                        "from": vec(pre_lo), "to": vec(pre_hi),
                        "origin": vec(translation), "rotation": rotation,
                        "material": obj.data.materials[0].name,
                        "expected_corners": [vec(c) for c in corners]}
                assert all(b-a > .001 for a,b in zip(pre_lo,pre_hi)), cube["name"]
                cubes.append(cube)
                expected.extend(corners)
                converted_points.extend(corners)
            raw = [AXIS @ (matrix @ v.co) * SCALE for v in obj.data.vertices]
            source_points.extend(raw)
            p0,p1 = bounds(raw)
            c0,c1 = bounds(expected)
            error = max(abs(a-b)/SCALE for a,b in zip(p0+p1,c0+c1))
            assert error < .12, (name, label, error)
            if matrix.translation.length > .001:
                pivot = translation
            else:
                pivot = (Vector(p0)+Vector(p1))/2
            parts.append({"name": label, "pivot": vec(pivot), "parent": "root",
                          "source_object": obj.name, "source_vertices": len(obj.data.vertices),
                          "method": method, "cube_count": len(local_boxes),
                          "bounds_max_deviation_m": round(error,6)})
        assert len({p["name"] for p in parts}) == len(parts)
        original_bounds, converted_bounds = bounds(source_points), bounds(converted_points)
        result["models"][name] = {"parts": parts, "cubes": cubes,
            "source_vertices": sum(len(o.data.vertices) for o in objects),
            "source_bounds_bb": [vec(v) for v in original_bounds],
            "converted_bounds_bb": [vec(v) for v in converted_bounds],
            "logical_vertices": 8*len(cubes), "quad_faces": 6*len(cubes),
            "triangles": 12*len(cubes), "render_vertices": 24*len(cubes),
            "note": "Each cube has 8 corners, or 24 vertices when split by face normals/UV. Internal touching faces are retained."}
        print("CONVERTED", name, len(parts), "parts", len(cubes), "cubes", flush=True)
    (output/"intermediate.json").write_text(json.dumps(result,indent=2)+"\n")


if __name__ == "__main__":
    main()
