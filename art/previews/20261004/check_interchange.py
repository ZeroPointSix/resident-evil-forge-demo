"""Reopen the saved Blend and reimport each OBJ with Blender 4."""

import json
from pathlib import Path

import bpy


root = Path(bpy.data.filepath).parent
assert bpy.data.filepath.endswith("monster_blockouts.blend")
stats = json.loads((root/"model_stats.json").read_text())
for name, expected in stats["models"].items():
    collection = bpy.data.collections[name]
    meshes = [obj for obj in collection.objects if obj.type == "MESH"]
    assert len(meshes) == expected["objects"]
    assert sum(len(obj.data.polygons) for obj in meshes) == expected["polygons"]
    assert list(bpy.data.objects[name+"_ROOT"].scale) == [1, 1, 1]
report = {"blend_reopened": True, "obj_reimported": {}}
for name, expected in stats["models"].items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=str(root/(name+".obj")), forward_axis="NEGATIVE_Y", up_axis="Z")
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    assert sum(len(obj.data.polygons) for obj in meshes) == expected["polygons"]
    report["obj_reimported"][name] = True
(root/"interchange_validation.json").write_text(json.dumps(report, indent=2)+"\n")
print("BLEND_AND_OBJ_REOPEN_OK", json.dumps(report))
