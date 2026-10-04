"""Original silhouette blockouts. Run with Blender 4, not in the game resource tree."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PARSER = argparse.ArgumentParser()
PARSER.add_argument("--output", default="art/previews/20261004/deliverables")
OPT = PARSER.parse_args(ARGS)
OUT = Path(OPT.output).resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert bpy.app.version[0] == 4, bpy.app.version_string
bpy.ops.wm.read_factory_settings(use_empty=True)
SCENE = bpy.context.scene
MODELS = {}
CURRENT = None


def material(name, rgb, roughness=0.78, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


M = {
    "coat": material("Coat / deep graphite green", (0.055, 0.115, 0.105)),
    "coat_edge": material("Coat / raised panels", (0.105, 0.185, 0.158)),
    "black": material("Rubber and dark leather", (0.023, 0.032, 0.038)),
    "metal": material("Oxidized brass", (0.44, 0.31, 0.12), 0.6, 0.25),
    "skin": material("Cold mineral skin", (0.38, 0.46, 0.45)),
    "shade": material("Recesses", (0.042, 0.048, 0.055)),
    "cloth": material("Torn work coat", (0.54, 0.57, 0.50)),
    "cloth_dark": material("Work coat shadows", (0.26, 0.32, 0.30)),
    "pants": material("Work trousers", (0.11, 0.17, 0.24)),
    "mutant": material("Mutation / main mass", (0.40, 0.10, 0.095)),
    "mutant_light": material("Mutation / planes", (0.60, 0.235, 0.18)),
    "mutant_dark": material("Mutation / joint recesses", (0.19, 0.043, 0.055)),
    "bone": material("Bone / warm ivory", (0.75, 0.68, 0.49)),
    "amber": material("Shoulder eye / amber", (0.92, 0.49, 0.065)),
    "licker": material("Crawler / terracotta", (0.47, 0.13, 0.14)),
    "licker_light": material("Crawler / raised planes", (0.69, 0.30, 0.26)),
    "tongue": material("Tongue / muted rose", (0.64, 0.14, 0.24)),
}


def begin(name):
    global CURRENT
    collection = bpy.data.collections.new(name)
    SCENE.collection.children.link(collection)
    root = bpy.data.objects.new(name + "_ROOT", None)
    collection.objects.link(root)
    CURRENT = {"collection": collection, "root": root, "objects": []}
    MODELS[name] = CURRENT


def register(obj, name, mat):
    obj.name = name
    for collection in list(obj.users_collection):
        collection.objects.unlink(obj)
    CURRENT["collection"].objects.link(obj)
    obj.parent = CURRENT["root"]
    obj.data.materials.append(M[mat])
    CURRENT["objects"].append(obj)
    return obj


def box(name, location, size, mat, bevel=0.025, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler = [math.radians(v) for v in rotation]
    if bevel:
        mod = obj.modifiers.new("Single facet edge", "BEVEL")
        mod.width = min(bevel, min(size) * 0.23)
        mod.segments = 1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return register(obj, name, mat)


def loft(name, rings, mat):
    """Closed, clipped-rectangle sections; each ring is z, width, depth, x, y."""
    verts = []
    for z, w, d, x, y in rings:
        a, b = w / 2, d / 2
        c = min(a, b) * 0.30
        ring = [(-a+c, -b), (a-c, -b), (a, -b+c), (a, b-c),
                (a-c, b), (-a+c, b), (-a, b-c), (-a, -b+c)]
        verts.extend((px+x, py+y, z) for px, py in ring)
    faces = [tuple(reversed(range(8)))]
    for j in range(len(rings) - 1):
        for i in range(8):
            faces.append((j*8+i, j*8+(i+1) % 8,
                          (j+1)*8+(i+1) % 8, (j+1)*8+i))
    faces.append(tuple((len(rings)-1)*8+i for i in range(8)))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    return register(obj, name, mat)


def beam(name, start, end, width, depth, mat, end_scale=0.78, bulge=1.04):
    a, b = Vector(start), Vector(end)
    length = (b-a).length
    obj = loft(name, [(0, width, depth, 0, 0),
                      (length*0.38, width*bulge, depth*bulge, 0, 0),
                      (length, width*end_scale, depth*end_scale, 0, 0)], mat)
    obj.location = a
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = (b-a).to_track_quat("Z", "Y")
    return obj


def tyrant():
    begin("tyrant")
    for side in [-1, 1]:
        s = side
        box(f"boot_{s}", (s*.30, -.12 if s == 1 else -.02, .17),
            (.42, .69, .34), "black", .055, (0, 0, s*-4))
        beam(f"shin_{s}", (s*.30, .06, .32), (s*.27, .06, 1.10),
             .30, .34, "black", .91)
        beam(f"thigh_{s}", (s*.26, .08, 1.00), (s*.24, .08, 1.55),
             .37, .42, "black", .90)
    loft("coat_chest", [(1.42, .84, .52, 0, .06), (1.85, .95, .61, 0, .03),
                         (2.34, 1.16, .70, 0, .015), (2.59, 1.00, .57, 0, .045)], "coat")
    for s in [-1, 1]:
        loft(f"split_coat_tail_{s}", [(.61, .50, .59, s*.33, .12),
             (1.01, .51, .60, s*.28, .085), (1.53, .44, .54, s*.235, .05)], "coat")
        box(f"hem_edge_{s}", (s*.33, -.195, .66), (.43, .065, .075), "coat_edge", .008)
        box(f"lapel_{s}", (s*.23, -.342, 2.26), (.25, .12, .64),
            "coat_edge", .022, (8, s*22, s*-7))
        beam(f"upper_sleeve_{s}", (s*.56, .015, 2.43), (s*.83, .035, 1.93),
             .43, .49, "coat", .79, 1.02)
        box(f"shoulder_yoke_{s}", (s*.63, .00, 2.49), (.43, .54, .18),
            "coat_edge", .035, (0, s*17, 0))
        beam(f"fore_sleeve_{s}", (s*.83, .035, 1.98), (s*.80, -.17, 1.39),
             .34, .39, "coat", .84)
        box(f"cuff_{s}", (s*.80, -.17, 1.40), (.34, .38, .16), "black", .018)
        box(f"fist_{s}", (s*.80, -.20, 1.22), (.31, .33, .33), "skin", .040)
        box(f"thumb_{s}", (s*.66, -.24, 1.22), (.095, .17, .20), "skin", .015)
        for i in range(3):
            box(f"knuckle_{s}_{i}", (s*.80+(i-1)*.080, -.365, 1.29),
                (.067, .03, .083), "skin", .007)
    box("waist_belt", (0, -.014, 1.61), (.97, .60, .14), "black", .012)
    box("belt_buckle", (0, -.327, 1.61), (.19, .035, .14), "metal", .008)
    box("buckle_inset", (0, -.349, 1.61), (.11, .015, .075), "black", 0)
    box("back_storm_panel", (0, .373, 2.29), (.94, .10, .29), "coat_edge", .028)
    box("back_center_seam", (0, .368, 1.08), (.036, .035, .80), "black", .004)
    beam("neck", (0, .025, 2.54), (0, -.02, 2.85), .35, .37, "skin", .96)
    loft("head", [(2.67, .32, .34, 0, -.062), (2.82, .44, .40, 0, -.06),
                  (3.01, .44, .39, 0, -.023), (3.11, .36, .34, 0, -.005)], "skin")
    for s in [-1, 1]:
        box(f"high_collar_{s}", (s*.29, .015, 2.68), (.18, .45, .29),
            "coat_edge", .018, (0, s*-14, 0))
        box(f"brow_{s}", (s*.12, -.271, 2.91), (.17, .076, .07), "skin", .008, (0, s*-5, 0))
        box(f"eye_recess_{s}", (s*.12, -.270, 2.874), (.104, .02, .030), "shade", 0)
    box("nose", (0, -.295, 2.82), (.090, .11, .13), "skin", .013)
    box("mouth_line", (0, -.247, 2.729), (.195, .016, .020), "shade", 0)
    brim = box("hat_brim", (0, -.015, 3.085), (.92, .68, .085), "black", .045, (3, 0, -3))
    loft("hat_pinched_crown", [(3.08, .56, .44, 0, .008),
                              (3.30, .50, .38, -.026, .04),
                              (3.35, .40, .30, -.022, .05)], "coat")
    box("hat_band", (0, -.002, 3.12), (.575, .449, .060), "black", .018)
    box("hat_band_clip", (-.25, -.191, 3.13), (.048, .028, .056), "metal", .006)


def birkin():
    begin("g1_birkin")
    for s in [-1, 1]:
        x = s*.27-.12
        foot_y = -.09 if s == -1 else .04
        box(f"boot_{s}", (x, foot_y-.12, .14), (.33, .56, .28), "black", .044)
        knee = (x-.03, -.09, .63)
        beam(f"shin_{s}", (x, foot_y, .22), knee, .27, .31, "pants", 1.03)
        beam(f"thigh_{s}", knee, (s*.19-.13, .075, 1.21), .35, .36, "pants", .9)
    loft("pelvis", [(1.03, .67, .44, -.13, .03), (1.31, .71, .48, -.13, .03)], "pants")
    loft("leaning_torso", [(1.22, .64, .43, -.14, .03), (1.58, .76, .50, -.17, .03),
                          (1.96, .85, .58, -.23, .05), (2.22, .80, .52, -.24, .065)], "cloth")
    loft("ragged_coat_left", [(.90, .24, .44, -.48, .13), (1.31, .36, .47, -.42, .03),
                             (1.82, .34, .49, -.46, .015)], "cloth")
    box("coat_back_fold", (-.14, .317, 1.59), (.57, .07, .68), "cloth_dark", .02, (4, -9, 0))
    box("shirt_opening", (-.04, -.245, 1.81), (.24, .06, .66), "mutant_dark", .014, (0, -14, 0))
    box("normal_lapel", (-.35, -.297, 2.00), (.15, .07, .37), "cloth_dark", .014, (0, -24, 0))
    beam("normal_upper_arm", (-.61, .035, 2.03), (-.83, -.01, 1.62), .27, .30, "cloth", .75)
    beam("normal_forearm", (-.83, -.01, 1.64), (-.88, -.21, 1.19), .22, .23, "skin", .76)
    box("normal_hand", (-.88, -.23, 1.05), (.22, .21, .27), "skin", .031)
    beam("neck", (-.27, .04, 2.15), (-.38, -.04, 2.40), .26, .29, "skin", .83)
    box("head", (-.40, -.08, 2.48), (.36, .36, .42), "skin", .070, (8, -13, -5))
    box("hair", (-.41, -.028, 2.686), (.35, .30, .065), "cloth_dark", .022, (8, -13, -5))
    for s in [-1, 1]:
        box(f"eye_slot_{s}", (-.40+s*.078, -.267, 2.515), (.069, .023, .027), "shade", 0)
    box("jaw", (-.42, -.17, 2.337), (.26, .26, .10), "skin", .026)
    loft("mutation_shoulder", [(1.91, .66, .59, .50, .045),
         (2.19, 1.05, .90, .60, .045), (2.52, 1.02, .88, .64, .065),
         (2.73, .64, .60, .63, .09)], "mutant")
    beam("mutation_upper_arm", (.80, .075, 2.29), (1.13, .13, 1.65),
         .64, .74, "mutant_light", .91, 1.12)
    box("mutation_elbow", (1.12, .14, 1.65), (.66, .66, .34), "mutant_dark", .08)
    beam("mutation_forearm", (1.13, .11, 1.72), (1.32, -.20, .86),
         .73, .70, "mutant", .86, 1.21)
    beam("forearm_ridge", (1.32, -.11, 1.63), (1.56, -.38, .94),
         .24, .24, "mutant_light", .7)
    box("mutation_palm", (1.31, -.24, .73), (.69, .50, .43), "mutant_light", .085, (0, 0, -7))
    for i in range(3):
        x = 1.08+i*.225
        beam(f"giant_finger_{i}", (x, -.29, .66), (x+.065, -.47, .32),
             .18, .18, "mutant", .66)
        beam(f"giant_claw_{i}", (x+.065, -.47, .34), (x+.12, -.64, .22),
             .105, .11, "bone", .06, .90)
    beam("giant_thumb", (1.02, -.24, .80), (.88, -.47, .51), .22, .22, "mutant", .66)
    beam("thumb_claw", (.89, -.47, .52), (.93, -.60, .36), .12, .12, "bone", .06)
    for i, (x, y, z) in enumerate([(.89, .27, 2.64), (1.03, .19, 2.40), (1.18, .22, 2.06)]):
        beam(f"shoulder_bone_{i}", (x, y, z), (x+.23, y+.07, z+.22), .17, .20, "bone", .04)
    beam("eye_socket", (.60, -.43, 2.38), (.60, -.53, 2.38), .56, .51, "mutant_dark", .92)
    beam("eye_sclera", (.60, -.54, 2.38), (.60, -.595, 2.38), .43, .38, "bone", .85)
    beam("eye_iris", (.61, -.60, 2.38), (.61, -.638, 2.38), .25, .26, "amber", .90)
    box("eye_pupil", (.61, -.665, 2.38), (.055, .027, .178), "shade", .008)
    box("eye_glint", (.66, -.680, 2.439), (.029, .010, .032), "bone", 0)


def licker():
    begin("licker")
    beam("rib_cage", (0, .60, .67), (0, -.53, .70), .79, .58, "licker", 1.13, 1.22)
    beam("hunched_back", (0, .51, .88), (0, -.34, .98), .52, .34, "licker_light", 1.10)
    box("pelvis", (0, .72, .53), (.71, .62, .51), "licker", .11, (6, 0, 0))
    for s in [-1, 1]:
        beam(f"front_upper_{s}", (s*.38, -.34, .76), (s*.93, -.56, 1.03),
             .34, .32, "licker_light", .68)
        box(f"front_elbow_{s}", (s*.94, -.56, 1.02), (.26, .29, .28), "bone", .045)
        beam(f"front_forearm_{s}", (s*.95, -.58, .99), (s*1.23, -1.03, .23),
             .22, .25, "licker", .68)
        box(f"front_hand_{s}", (s*1.24, -1.11, .18), (.34, .34, .17), "licker_light", .025)
        beam(f"rear_thigh_{s}", (s*.29, .56, .62), (s*.87, .87, .49),
             .43, .43, "licker_light", .66, 1.14)
        beam(f"rear_shin_{s}", (s*.88, .88, .49), (s*.79, 1.34, .18),
             .23, .24, "licker", .70)
        box(f"rear_foot_{s}", (s*.81, 1.39, .14), (.34, .38, .16), "licker_light", .025)
        for i in range(3):
            x = s*1.24+(i-1)*.115
            beam(f"front_claw_{s}_{i}", (x, -1.22, .18), (x+s*.07, -1.58-(i % 2)*.07, .07),
                 .085, .09, "bone", .04, .92)
            x2 = s*.82+(i-1)*.11
            beam(f"rear_claw_{s}_{i}", (x2, 1.47, .13), (x2+s*.09, 1.73, .06),
                 .077, .08, "bone", .04, .92)
        for i in range(3):
            box(f"rib_plane_{s}_{i}", (s*.43, -.12+i*.24, .66), (.075, .105, .26),
                "licker_light", .012, (13, s*17, 0))
    beam("low_neck", (0, -.47, .69), (0, -.83, .58), .52, .40, "licker_dark" if "licker_dark" in M else "mutant_dark", 1.03)
    box("eyeless_skull", (0, -.99, .70), (.82, .74, .51), "licker_light", .10, (-7, 0, 0))
    box("jaw_shadow", (0, -1.245, .47), (.64, .29, .18), "shade", .033)
    box("lower_jaw", (0, -1.12, .385), (.62, .60, .11), "licker", .028, (-4, 0, 0))
    for i in range(5):
        x = (i-2)*.11
        beam(f"upper_tooth_{i}", (x, -1.352, .57), (x, -1.372, .455), .061, .070, "bone", .05, .9)
    for i in range(4):
        x = (i-1.5)*.12
        box(f"skull_tile_{i}", (x, -1.01+(i % 2)*.10, .960), (.105, .33, .055),
            "bone" if i == 0 else "licker_light", .018, (-7, 0, 0))
    for i in range(6):
        box(f"spine_plate_{i}", (0, -.30+i*.205, 1.085-i*.043), (.20, .15, .085),
            "bone", .020, (-12, 0, 0))
    points = [(0, -1.35, .43), (.02, -1.80, .35), (.08, -2.27, .24),
              (.29, -2.66, .20), (.60, -2.91, .27), (.83, -3.04, .34)]
    for i, (a, b) in enumerate(zip(points, points[1:])):
        beam(f"tongue_{i}", a, b, .15-i*.017, .095-i*.009, "tongue", .83, 1.0)


def bounds(model):
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ Vector(v) for obj in model["objects"] for v in obj.bound_box]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    return lo, hi


def visible(names):
    for name, model in MODELS.items():
        for obj in model["objects"]:
            obj.hide_render = name not in names


def setup_studio():
    SCENE.render.engine = "CYCLES"
    SCENE.cycles.device = "CPU"
    SCENE.cycles.samples = 32
    SCENE.cycles.use_denoising = True
    SCENE.cycles.max_bounces = 5
    SCENE.render.threads_mode = "FIXED"
    SCENE.render.threads = 4
    SCENE.render.image_settings.file_format = "PNG"
    SCENE.render.image_settings.color_mode = "RGB"
    SCENE.render.film_transparent = False
    SCENE.view_settings.view_transform = "AgX"
    SCENE.world = bpy.data.worlds.new("Neutral studio")
    SCENE.world.use_nodes = True
    SCENE.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.76, .80, .83, 1)
    SCENE.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .65
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.018))
    floor = bpy.context.object
    floor.name = "STUDIO_FLOOR"
    floor.data.materials.append(material("Studio floor", (.69, .73, .74)))
    for name, location, power, size, color in [
        ("KEY", (-4, -5, 7), 1400, 5, (1, .92, .82)),
        ("FILL", (5, -2, 4), 950, 4, (.77, .88, 1)),
        ("RIM", (2, 5, 6), 1700, 4, (1, 1, 1))]:
        light = bpy.data.lights.new(name, "AREA")
        light.energy, light.shape, light.size = power, "DISK", size
        light.color = color
        obj = bpy.data.objects.new(name, light)
        SCENE.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector((0, 0, 1.3))-obj.location).to_track_quat("-Z", "Y").to_euler()
    camera = bpy.data.cameras.new("Orthographic cameras")
    obj = bpy.data.objects.new("CAMERA", camera)
    SCENE.collection.objects.link(obj)
    SCENE.camera = obj
    camera.type = "ORTHO"
    camera.sensor_fit = "HORIZONTAL"
    SCENE.unit_settings.system = "METRIC"
    SCENE.unit_settings.scale_length = 1


def render(filename, target, offset, scale, size=(1024, 1024)):
    camera = SCENE.camera
    camera.location = Vector(target)+Vector(offset)
    camera.rotation_euler = (Vector(target)-camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = scale
    camera.data.lens = 50
    SCENE.render.resolution_x, SCENE.render.resolution_y = size
    SCENE.render.resolution_percentage = 100
    SCENE.render.filepath = str(OUT/filename)
    bpy.context.view_layer.update()
    from bpy_extras.object_utils import world_to_camera_view
    projected = [world_to_camera_view(SCENE, camera, obj.matrix_world @ v.co)
                 for model in MODELS.values() for obj in model["objects"]
                 if not obj.hide_render for v in obj.data.vertices]
    assert all(.015 < p.x < .985 and .015 < p.y < .985 for p in projected), filename
    bpy.ops.render.render(write_still=True)
    print("RENDER_OK", filename, flush=True)


def main():
    tyrant()
    birkin()
    licker()
    bpy.context.view_layer.update()
    stats = {"tool": "Blender " + bpy.app.version_string, "render_engine": "Cycles CPU",
             "source_commit": os.environ.get("GITHUB_SHA", "local"),
             "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "unit": "1 Blender unit = 1 proposed metre (not official canon)",
             "baseline": "deb10db8a08361041c07bd7a23abb1cf22812ba5",
             "status": "original silhouette blockout; not game-ready", "models": {}}
    import bmesh
    for name, model in MODELS.items():
        lo, hi = bounds(model)
        polygons = triangles = vertices = 0
        for obj in model["objects"]:
            obj.data.calc_loop_triangles()
            polygons += len(obj.data.polygons)
            triangles += len(obj.data.loop_triangles)
            vertices += len(obj.data.vertices)
            assert min(obj.dimensions) > .004, obj.name
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            assert all(e.is_manifold for e in bm.edges), obj.name
            bm.free()
        stats["models"][name] = {"objects": len(model["objects"]), "polygons": polygons,
            "triangles": triangles, "vertices": vertices,
            "bounds_min": list(lo), "bounds_max": list(hi),
            "dimensions_xyz_m": [round(v, 4) for v in hi-lo],
            "all_parts_closed_manifold": True}
        bpy.ops.object.select_all(action="DESELECT")
        for obj in model["objects"]:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = model["objects"][0]
        bpy.ops.wm.obj_export(filepath=str(OUT/(name+".obj")), export_selected_objects=True,
                              export_materials=True, forward_axis="NEGATIVE_Y", up_axis="Z")
    setup_studio()
    for name, model in MODELS.items():
        visible([name])
        lo, hi = bounds(model)
        center = (lo+hi)/2
        scale = max(hi.z-lo.z, hi.x-lo.x, hi.y-lo.y)*1.18
        stats["models"][name]["orthographic_scale"] = scale
        for label, offset in [("front", (0, -12, 0)), ("side", (12, 0, 0)), ("back", (0, 12, 0))]:
            render(name+"_"+label+".png", center, offset, scale)
        render(name+"_three_quarter.png", center, (8, -12, 6), scale*.94)
    visible(MODELS.keys())
    for name, x, angle in [("tyrant", -3.5, -12), ("g1_birkin", -.50, -15), ("licker", 3.15, 62)]:
        MODELS[name]["root"].location.x = x
        MODELS[name]["root"].rotation_euler.z = math.radians(angle)
    bpy.context.view_layer.update()
    all_bounds = [bounds(m) for m in MODELS.values()]
    x0 = min(lo.x for lo, hi in all_bounds)
    x1 = max(hi.x for lo, hi in all_bounds)
    z0 = min(lo.z for lo, hi in all_bounds)
    z1 = max(hi.z for lo, hi in all_bounds)
    lineup_width = max((x1-x0)*1.15, (z1-z0)*(2400/1050)*1.20)
    render("lineup.png", ((x0+x1)/2, 0, (z0+z1)/2), (0, -20, 0), lineup_width, (2400, 1050))
    stats["lineup"] = {"projection": "orthographic", "same_world_scale": True,
                       "vertical_axis": "Z", "unit_m": 1, "orthographic_width": lineup_width,
                       "camera_bounds_verified": True,
                       "model_scales": {n: list(m["root"].scale) for n, m in MODELS.items()}}
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"monster_blockouts.blend"), compress=True)
    (OUT/"model_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2)+"\n")
    print("COMPLETE", json.dumps(stats), flush=True)


if __name__ == "__main__":
    main()
