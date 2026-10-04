"""Render final GEO geometry and cross-check against real Blockbench vertices."""
import itertools
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Vector
from PIL import Image

OUT = Path(sys.argv[sys.argv.index("--")+1])
AXIS_INV = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
NAMES = ("tyrant", "g1_birkin", "licker")
bpy.ops.wm.read_factory_settings(use_empty=True)
SCENE = bpy.context.scene
MODELS = {}
REPORT = {"renderer": "Blender "+bpy.app.version_string, "input": "final .geo.json and palette PNG",
          "all_model_scales": [1, 1, 1], "game_runtime_tested": False, "models": {}}


def linear(value):
    value /= 255
    return value/12.92 if value <= .04045 else ((value+.055)/1.055)**2.4


def material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = .78
    return mat


def model(name):
    geo = json.loads((OUT/(name+".geo.json")).read_text())["minecraft:geometry"][0]
    expected = list(json.loads((OUT/(name+"_bb_vertices.json")).read_text()).values())
    texture = Image.open(OUT/(name+"_palette.png")).convert("RGB")
    root = bpy.data.objects.new(name+"_ROOT", None)
    SCENE.collection.objects.link(root)
    objects, mats = [], {}
    maximum_error = 0
    for bone in geo["bones"]:
        assert not any(bone.get("rotation", [0, 0, 0])), "Rest-pose bones must have zero rotation"
        for cube in bone.get("cubes", []):
            origin, size = cube["origin"], cube["size"]
            a = Vector((-origin[0]-size[0], origin[1], origin[2]))
            b = a+Vector(size)
            p = cube.get("pivot", [0, 0, 0])
            pivot = Vector((-p[0], p[1], p[2]))
            r = cube.get("rotation", [0, 0, 0])
            rotation = Euler(tuple(math.radians(v) for v in (-r[0], -r[1], r[2])), "XYZ").to_matrix()
            bb_points = [rotation@(Vector(v)-pivot)+pivot for v in itertools.product(*zip(a, b))]
            for v in bb_points:
                error = min((v-Vector(e)).length for e in expected[len(objects)])
                maximum_error = max(error, maximum_error)
            vertices = [AXIS_INV@v/16 for v in bb_points]
            faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
                     (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
            mesh = bpy.data.meshes.new(bone["name"])
            mesh.from_pydata(vertices, [], faces)
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            assert all(e.is_manifold for e in bm.edges)
            bm.to_mesh(mesh)
            bm.free()
            obj = bpy.data.objects.new(bone["name"], mesh)
            SCENE.collection.objects.link(obj)
            obj.parent = root
            uv = cube["uv"]["north"]["uv"]
            rgb = texture.getpixel((int(uv[0]+1), int(uv[1]+1)))
            if rgb not in mats:
                mats[rgb] = material(name+str(rgb), [linear(v) for v in rgb])
            obj.data.materials.append(mats[rgb])
            objects.append(obj)
    assert maximum_error < .002, (name, maximum_error)
    REPORT["models"][name] = {"cube_count": len(objects), "max_blockbench_corner_error_units": maximum_error,
                              "each_cube_closed": True}
    MODELS[name] = {"root": root, "objects": objects}


for name in NAMES:
    model(name)
SCENE.render.engine = "CYCLES"
SCENE.cycles.device = "CPU"
SCENE.cycles.samples = 96
SCENE.cycles.use_denoising = False
SCENE.cycles.max_bounces = 4
SCENE.render.threads_mode = "FIXED"
SCENE.render.threads = 4
SCENE.render.image_settings.file_format = "PNG"
SCENE.render.image_settings.color_mode = "RGB"
SCENE.render.resolution_x = 2400
SCENE.render.resolution_y = 1050
SCENE.render.resolution_percentage = 100
SCENE.view_settings.view_transform = "AgX"
SCENE.world = bpy.data.worlds.new("Neutral studio")
SCENE.world.use_nodes = True
SCENE.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.76, .80, .83, 1)
SCENE.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .65
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.035))
bpy.context.object.data.materials.append(material("Floor", (.69, .73, .74)))
for name, loc, power, color in [
        ("Key", (-4, -5, 7), 1400, (1, .92, .82)),
        ("Fill", (5, -2, 4), 950, (.77, .88, 1)),
        ("Rim", (2, 5, 6), 1700, (1, 1, 1))]:
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size, data.color = power, "DISK", 5, color
    obj = bpy.data.objects.new(name, data)
    SCENE.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector((0, 0, 1.3))-obj.location).to_track_quat("-Z", "Y").to_euler()
for name, x, angle in [("tyrant", -3.5, -12), ("g1_birkin", -.50, -15), ("licker", 3.30, 62)]:
    root = MODELS[name]["root"]
    root.location.x = x
    root.rotation_euler.z = math.radians(angle)
bpy.context.view_layer.update()
points = [o.matrix_world@v.co for m in MODELS.values() for o in m["objects"] for v in o.data.vertices]
lo = Vector([min(p[a] for p in points) for a in range(3)])
hi = Vector([max(p[a] for p in points) for a in range(3)])
target = Vector(((lo.x+hi.x)/2, 0, (lo.z+hi.z)/2))
data = bpy.data.cameras.new("Same-scale orthographic")
data.type, data.sensor_fit = "ORTHO", "HORIZONTAL"
data.ortho_scale = max((hi.x-lo.x)*1.16, (hi.z-lo.z)*(2400/1050)*1.20)
camera = bpy.data.objects.new("Camera", data)
SCENE.collection.objects.link(camera)
SCENE.camera = camera
camera.location = target+Vector((0, -20, 0))
camera.rotation_euler = (target-camera.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
for name, m in MODELS.items():
    projected = [world_to_camera_view(SCENE, camera, o.matrix_world@v.co)
                 for o in m["objects"] for v in o.data.vertices]
    assert all(.02<p.x<.98 and .02<p.y<.98 for p in projected), name
    REPORT["models"][name]["screen_center_x"] = 2400*(min(p.x for p in projected)+max(p.x for p in projected))/2
    REPORT["models"][name]["camera_bounds_passed"] = True
SCENE.render.filepath = str(OUT/"converted_lineup_raw.png")
bpy.ops.render.render(write_still=True)
(OUT/"render_validation.json").write_text(json.dumps(REPORT, indent=2)+"\n")
print("GEO_RENDER_VALIDATED", json.dumps(REPORT), flush=True)
