#!/usr/bin/env python3
"""Bind the approved blockouts to the existing gameplay animation contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

from creature_assets_lib import build_blockbench_animation, get_models, keyframes, stable_uuid
from tyrant_phase_assets import upgrade_tyrant


ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "art/blockbench/20261004"
ASSETS = ROOT / "src/main/resources/assets/re_demo"
SOURCE_COMMIT = "d28b9bdd7abd56b8aadaf47fc7414212fd2eb181"


def turn(point):
    return [-point[0], point[1], -point[2]]


def orient_cube(cube):
    result = copy.deepcopy(cube)
    x, y, z = result["origin"]
    sx, _, sz = result["size"]
    result["origin"] = [-x - sx, y, -z - sz]
    if "pivot" in result:
        result["pivot"] = turn(result["pivot"])
    if "rotation" in result:
        rx, ry, rz = result["rotation"]
        result["rotation"] = [-rx, ry, -rz]
    return result


def bind_parts(creature, parts):
    bindings = {}
    for name in parts:
        if creature == "tyrant":
            if name.startswith("hat_"):
                target = "hat"
            elif name in ("head", "nose", "mouth_line") or name.startswith(("brow_", "eye_recess_")):
                target = "head"
            elif name == "neck" or name.startswith("high_collar_"):
                target = "neck"
            elif name.startswith(("split_coat_tail_", "hem_edge_")) or name == "back_center_seam":
                target = "coat_intact"
            elif name.startswith(("thigh_", "shin_", "boot_", "shoulder_yoke_", "upper_sleeve_", "fore_sleeve_", "cuff_", "fist_", "thumb_", "knuckle_")):
                side = "l" if "_1" in name and "_-1" not in name else "r"
                target = next(value for prefix, value in (
                    ("thigh", "thigh"), ("shin", "shin"), ("boot", "foot"),
                    ("shoulder_yoke", "shoulder"), ("upper_sleeve", "upper_arm"),
                    ("fore_sleeve", "forearm"), ("cuff", "forearm"),
                    ("fist", "hand"), ("thumb", "hand"), ("knuckle", "hand"),
                ) if name.startswith(prefix)) + "_" + side
            else:
                target = "torso"
        elif creature == "g1_birkin":
            if name in ("eye_sclera", "eye_iris", "eye_pupil", "eye_glint"):
                target = "eye_open"
            elif name in ("eye_socket", "mutation_shoulder") or name.startswith("shoulder_bone_"):
                target = "right_shoulder"
            elif name == "mutation_upper_arm":
                target = "right_upper_arm"
            elif name in ("mutation_elbow", "mutation_forearm", "forearm_ridge"):
                target = "right_forearm"
            elif name.startswith("giant_") or name in ("mutation_palm", "thumb_claw"):
                target = "right_hand"
            elif name.startswith("normal_upper"):
                target = "left_upper_arm"
            elif name.startswith("normal_forearm"):
                target = "left_forearm"
            elif name == "normal_hand":
                target = "left_hand"
            elif name in ("head", "hair", "jaw") or name.startswith("eye_slot_"):
                target = "head"
            elif name == "neck":
                target = "neck"
            elif name.startswith(("thigh_", "shin_", "boot_")):
                side = "r" if name.endswith("_-1") else "l"
                target = ("foot" if name.startswith("boot_") else name.split("_")[0]) + "_" + side
            else:
                target = "torso"
        else:
            if name == "eyeless_skull" or name.startswith("upper_tooth_") or name == "jaw_shadow":
                target = "head"
            elif name.startswith("skull_tile_"):
                target = "brain"
            elif name == "lower_jaw":
                target = "jaw"
            elif name == "low_neck":
                target = "neck"
            elif name.startswith("tongue_"):
                target = {0: "tongue_base", 1: "tongue_mid"}.get(int(name[-1]), "tongue_tip")
            elif name.startswith(("front_", "rear_")):
                side = "r" if "_-1" in name else "l"
                kind = "_".join(name.split("_")[:2])
                target = {"front_upper": "upper_arm", "front_elbow": "forearm",
                          "front_forearm": "forearm", "front_hand": "claw", "front_claw": "claw",
                          "rear_thigh": "thigh", "rear_shin": "shin", "rear_foot": "foot",
                          "rear_claw": "foot"}[kind] + "_" + side
            elif name == "pelvis":
                target = "pelvis"
            else:
                target = "chest"
        bindings[name] = target
    return bindings


def joint_pivots(creature, parts):
    p = lambda name: parts[name]["pivot"]
    if creature == "tyrant":
        result = {"root": [0, 0, 0], "pelvis": [0, 25.76, 0], "torso": [0, 25.76, 0],
                  "chest": [0, 34, 0], "neck": p("neck"), "head": [0, 43, 0.704],
                  "hat": p("hat_brim"), "coat_intact": [0, 25.76, 0], "coat_torn": [0, 25.76, 0]}
        for sign, side in ((-1, "r"), (1, "l")):
            for joint, part in (("shoulder", "shoulder_yoke"), ("upper_arm", "upper_sleeve"),
                                ("forearm", "fore_sleeve"), ("hand", "fist"),
                                ("thigh", "thigh"), ("shin", "shin"), ("foot", "boot")):
                result[joint + "_" + side] = p(f"{part}_{sign}")
            result["thigh_" + side] = [-sign * 4.16, 24, -1.28]
    elif creature == "g1_birkin":
        result = {"root": [0, 0, 0], "pelvis": p("pelvis"), "torso": p("pelvis"),
                  "chest": [2.24, 32, -0.8], "neck": p("neck"), "head": [6.4, 36.32, 1.28],
                  "right_shoulder": p("mutation_shoulder"), "right_upper_arm": p("mutation_upper_arm"),
                  "right_forearm": p("mutation_elbow"), "right_hand": p("mutation_palm"),
                  "eye_open": p("eye_sclera"), "eye_closed": p("eye_sclera"),
                  "left_shoulder": p("normal_upper_arm"), "left_upper_arm": p("normal_upper_arm"),
                  "left_forearm": p("normal_forearm"), "left_hand": p("normal_hand")}
        for sign, side in ((-1, "r"), (1, "l")):
            for joint, part in (("thigh", "thigh"), ("shin", "shin"), ("foot", "boot")):
                result[joint + "_" + side] = p(f"{part}_{sign}")
            result["thigh_" + side][1] = 18.72
    else:
        result = {"root": [0, 0, 0], "pelvis": p("pelvis"), "spine": p("pelvis"),
                  "chest": [0, 11.04, -5.6], "neck": p("low_neck"),
                  "head": [0, 11.2, 11.2], "jaw": [0, 7.52, 12.8],
                  "brain": p("eyeless_skull"), "tongue_base": p("tongue_0"),
                  "tongue_mid": p("tongue_1"), "tongue_tip": p("tongue_2")}
        for sign, side in ((-1, "r"), (1, "l")):
            for joint, part in (("shoulder", "front_upper"), ("upper_arm", "front_upper"),
                                ("forearm", "front_elbow"), ("claw", "front_hand"),
                                ("thigh", "rear_thigh"), ("shin", "rear_shin"), ("foot", "rear_foot")):
                result[joint + "_" + side] = p(f"{part}_{sign}")
    return {name: turn(value) for name, value in result.items()}


def retarget_attacks(creature, animations):
    def bones(name):
        return animations[f"animation.{creature}.{name}"]["bones"]

    def rotation(*samples):
        return {"rotation": keyframes(*samples)}

    if creature == "tyrant":
        bones("punch")["upper_arm_r"] = rotation(
            (0, [0, 0, 0]), (.5, [25, 0, 12]), (.8, [-55, 0, -8]),
            (1.2, [-20, 0, 8]), (1.6, [0, 0, 0]))
        bones("punch")["forearm_r"] = rotation(
            (0, [0, 0, 0]), (.5, [-70, 0, 0]), (.8, [-20, 0, 0]), (1.6, [0, 0, 0]))
        for action, names in {"shove": ("upper_arm_l", "upper_arm_r"),
                              "break": ("upper_arm_r", "forearm_r"),
                              "charge": ("torso",)}.items():
            for name in names:
                for value in bones(action)[name]["rotation"].values():
                    value[0] = -value[0]
    elif creature == "g1_birkin":
        # Move descendants of the shoulder only: the exposed eye's ancestors
        # are held at rest by CreatureModel and must not cancel the attack.
        bones("slam").clear()
        bones("slam").update({
            "right_upper_arm": rotation((0, [0, 0, 0]), (.55, [120, 0, 0]),
                                         (.9, [-35, 10, 0]), (1.2, [-35, 10, 0]), (1.8, [0, 0, 0])),
            "right_forearm": rotation((0, [0, 0, 0]), (.55, [20, 0, 0]),
                                       (.9, [5, 0, 0]), (1.2, [5, 0, 0]), (1.8, [0, 0, 0])),
        })
        bones("sweep").clear()
        bones("sweep").update({
            "right_upper_arm": rotation((0, [0, 0, 0]), (.65, [-20, -45, 0]),
                                         (1, [-25, 50, 0]), (1.45, [-25, 65, 0]), (2, [0, 0, 0])),
            "right_forearm": rotation((0, [0, 0, 0]), (.65, [-20, -20, 0]),
                                       (1, [-25, 25, 0]), (1.45, [-25, 25, 0]), (2, [0, 0, 0])),
        })
        bones("grab").clear()
        bones("grab").update({
            "right_upper_arm": rotation((0, [0, 0, 0]), (.45, [15, -10, 0]),
                                         (.75, [-30, 15, 0]), (1.3, [-10, 10, 0]),
                                         (1.5, [-45, 15, 0]), (2, [0, 0, 0])),
            "right_forearm": rotation((0, [0, 0, 0]), (.45, [-45, 0, 0]),
                                       (.75, [-25, 0, 0]), (1.3, [-60, 0, 0]),
                                       (1.5, [-5, 0, 0]), (2, [0, 0, 0])),
            "right_hand": {"scale": keyframes((0, [1, 1, 1]), (.75, [1.1, 1.1, 1.1]),
                                               (1.3, [.88, .88, .88]), (1.5, [1.1, 1.1, 1.1]), (2, [1, 1, 1]))},
        })
    else:
        bones("claw").update({
            "chest": rotation((0, [0, 0, 0]), (.25, [0, -5, 0]),
                               (.45, [0, 0, 0]), (1, [0, 0, 0])),
            "upper_arm_l": rotation((0, [0, 0, 0]), (.25, [10, -15, 8]),
                                     (.45, [-25, 45, -8]), (1, [0, 0, 0])),
            "forearm_l": rotation((0, [0, 0, 0]), (.25, [-60, 0, 0]),
                                   (.45, [-15, 0, 0]), (1, [0, 0, 0])),
            "claw_l": rotation((0, [0, 0, 0]), (.25, [0, 0, 15]),
                                (.45, [0, 0, -10]), (1, [0, 0, 0])),
        })


def animation_data(spec):
    result = copy.deepcopy(spec.animations)
    # The approved mesh already contains its characteristic leaning/crouched pose.
    for bone, tracks in result[f"animation.{spec.creature_id}.idle"]["bones"].items():
        if "rotation" in tracks:
            baseline = list(tracks["rotation"]["0"])
            tracks["rotation"] = {time: [v - b for v, b in zip(values, baseline)]
                                  for time, values in tracks["rotation"].items()}
    if spec.creature_id == "g1_birkin":
        for animation in result.values():
            for tracks in animation["bones"].values():
                for channel, samples in tracks.items():
                    if channel == "rotation":
                        for value in samples.values():
                            value[1], value[2] = -value[1], -value[2]
                    elif channel == "position":
                        for value in samples.values():
                            value[0] = -value[0]
    retarget_attacks(spec.creature_id, result)
    return {"format_version": "1.8.0", "animations": result}


def bb_source(creature, geometry, animations, spec):
    result = json.loads((APPROVED / f"{creature}.bbmodel").read_text())
    elements, nodes = [], {}
    hidden = {"coat_torn", "tyrant_eye", "mutant_chest", "mutant_shoulder", "mutant_upper_r", "mutant_upper_l", "mutant_forearm_r", "mutant_forearm_l", "blade_r", "blade_l"} if creature == "tyrant" else {"eye_closed"}
    for bone in geometry["bones"]:
        pivot = bone["pivot"]
        node = {"name": bone["name"], "origin": [-pivot[0], pivot[1], pivot[2]],
                "rotation": [0, 0, 0], "uuid": stable_uuid(f"{creature}:bone:{bone['name']}"),
                "export": True, "isOpen": True, "visibility": bone["name"] not in hidden, "children": []}
        nodes[bone["name"]] = node
        for cube in bone.get("cubes", []):
            origin, size = cube["origin"], cube["size"]
            a = [-origin[0] - size[0], origin[1], origin[2]]
            pivot = cube.get("pivot", [0, 0, 0])
            rotation = cube.get("rotation", [0, 0, 0])
            uid = stable_uuid(f"{creature}:cube:{cube['name']}")
            faces = {}
            for face, uv in cube["uv"].items():
                u, v = uv["uv"]
                w, h = uv["uv_size"]
                faces[face] = {"uv": [u, v, u + w, v + h], "texture": 0}
            elements.append({"name": cube["name"], "type": "cube", "uuid": uid,
                             "from": a, "to": [v + s for v, s in zip(a, size)],
                             "origin": [-pivot[0], pivot[1], pivot[2]],
                             "rotation": [-rotation[0], -rotation[1], rotation[2]],
                             "box_uv": False, "autouv": 0, "faces": faces})
            node["children"].append(uid)
    roots = []
    for bone in geometry["bones"]:
        if bone.get("parent"):
            nodes[bone["parent"]]["children"].append(nodes[bone["name"]])
        else:
            roots.append(nodes[bone["name"]])
    spec.animations = animations["animations"]
    result.update(name=creature, model_identifier=f"geometry.re_demo.{creature}",
                  elements=elements, outliner=roots, animations=[
                      build_blockbench_animation(spec, name, data) for name, data in spec.animations.items()])
    result["textures"][0].update(name=f"{creature}.png", path=f"../src/main/resources/assets/re_demo/textures/entity/{creature}.png")
    return result


def assemble(creature, spec):
    source = json.loads((APPROVED / f"{creature}.geo.json").read_text())
    geometry = copy.deepcopy(source["minecraft:geometry"][0])
    parts = {bone["name"]: copy.deepcopy(bone) for bone in geometry["bones"] if bone["name"] != "root"}
    bindings = bind_parts(creature, parts)
    pivots = joint_pivots(creature, copy.deepcopy(parts))
    bones = [{"name": name, "pivot": pivots[name], **({"parent": bone.parent} if bone.parent else {})}
             for name, bone in spec.bones.items()]
    if creature == "licker":
        next(b for b in bones if b["name"] == "tongue_base")["parent"] = "head"
    for name, part in parts.items():
        cubes = [dict(orient_cube(cube), name=f"{name}_{index:03d}") for index, cube in enumerate(part.get("cubes", []))]
        bones.append({"name": "part_" + name, "parent": bindings[name], "pivot": turn(part["pivot"]), "cubes": cubes})
    if creature == "tyrant":
        for part in list(bones):
            if part.get("parent") != "coat_intact":
                continue
            torn = copy.deepcopy(part)
            torn["name"] = "torn_" + part["name"]
            torn["parent"] = "coat_torn"
            for cube in torn["cubes"]:
                cube["name"] = "torn_" + cube["name"]
                cube["origin"][1] = 26 + (cube["origin"][1] - 26) * .64
                cube["size"][1] *= .64
                if "pivot" in cube:
                    cube["pivot"][1] = 26 + (cube["pivot"][1] - 26) * .64
            bones.append(torn)
    if creature == "g1_birkin":
        skin_uv = parts["mutation_shoulder"]["cubes"][0]["uv"]
        for part in list(bones):
            if part.get("parent") != "eye_open":
                continue
            closed = copy.deepcopy(part)
            closed["name"] = "closed_" + part["name"]
            closed["parent"] = "eye_closed"
            for cube in closed["cubes"]:
                cube["name"] = "closed_" + cube["name"]
                cube["uv"] = copy.deepcopy(skin_uv)
            bones.append(closed)
    geometry["bones"] = bones
    geometry["description"]["identifier"] = f"geometry.re_demo.{creature}"
    geometry["description"]["visible_bounds_width"] = 8
    geometry["description"]["visible_bounds_height"] = 6
    geometry["description"]["visible_bounds_offset"] = [0, 1.5, 0]
    animations = animation_data(spec)
    if creature == "tyrant":
        upgrade_tyrant(geometry, animations)
    return {"format_version": "1.12.0", "minecraft:geometry": [geometry]}, animations


def generate_all(root=ROOT, only=None):
    if root != ROOT:
        raise ValueError("Generate from this script's checked-out repository")
    report = {"source_commit": SOURCE_COMMIT, "source_directory": str(APPROVED.relative_to(ROOT)),
              "source_to_runtime_y_rotation_degrees": 180, "creatures": {}}
    for creature, spec in get_models().items():
        if only is not None and creature != only:
            continue
        model, animations = assemble(creature, spec)
        texture = APPROVED / f"{creature}_palette.png"
        project = bb_source(creature, model["minecraft:geometry"][0], animations, spec)
        outputs = {ASSETS / "geo" / f"{creature}.geo.json": model,
                   ASSETS / "animations" / f"{creature}.animation.json": animations,
                   ROOT / "art" / f"{creature}.bbmodel": project}
        for path, data in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")
        (ASSETS / "textures/entity").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(texture, ASSETS / "textures/entity" / f"{creature}.png")
        report["creatures"][creature] = {
            "approved_geometry_sha256": hashlib.sha256((APPROVED / f"{creature}.geo.json").read_bytes()).hexdigest(),
            "runtime_geometry_sha256": hashlib.sha256((ASSETS / "geo" / f"{creature}.geo.json").read_bytes()).hexdigest(),
            "bones": len(model["minecraft:geometry"][0]["bones"]),
            "cubes": sum(len(b.get("cubes", [])) for b in model["minecraft:geometry"][0]["bones"]),
        }
    if only is not None:
        existing = json.loads((ROOT / "art/runtime_remodel_manifest.json").read_text())
        existing["creatures"].update(report["creatures"])
        report = existing
    (ROOT / "art/runtime_remodel_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=("tyrant", "licker", "g1_birkin"))
    print(json.dumps(generate_all(only=parser.parse_args().only), indent=2))
