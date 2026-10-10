"""Independent, dependency-free checks against the approved art baseline."""

import base64
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "art/blockbench/20261004"
ASSETS = ROOT / "src/main/resources/assets/re_demo"
HASHES = {
    "tyrant": "2be45369e25aae3923a59f56c2f12d304f3c71a67675cad5d1739308e56b3d8f",
    "g1_birkin": "c3f850346a63e51d23c1387548709d956c41ee6002808c2de2c61ccac1880b0f",
    "licker": "ed51c3bcb7dc7b900d86e30c6675581fd0c35418ce77c753f79846640b3ca13d",
}


def read(path):
    return json.loads(path.read_text())


def bones(path):
    return {b["name"]: b for b in read(path)["minecraft:geometry"][0]["bones"]}


def vertices(cube):
    """Bedrock cube -> editor XYZ rotation -> logical model coordinates."""
    origin, size = cube["origin"], cube["size"]
    pivot = cube.get("pivot", [0, 0, 0])
    pivot = [-pivot[0], pivot[1], pivot[2]]
    rx, ry, rz = cube.get("rotation", [0, 0, 0])
    rx, ry, rz = map(math.radians, (-rx, -ry, rz))
    points = []
    for ix, iy, iz in itertools.product((0, 1), repeat=3):
        x = -origin[0] - size[0] + ix * size[0] - pivot[0]
        y = origin[1] + iy * size[1] - pivot[1]
        z = origin[2] + iz * size[2] - pivot[2]
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
        x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
        points.append([-(x + pivot[0]), y + pivot[1], z + pivot[2]])
    return points


def sample(track, time, default):
    if track is None:
        return default
    keys = sorted((float(key), value) for key, value in track.items())
    if time <= keys[0][0]:
        return keys[0][1]
    for (a, start), (b, end) in zip(keys, keys[1:]):
        if time <= b:
            return [x + (y - x) * (time - a) / (b - a) for x, y in zip(start, end)]
    return keys[-1][1]


def posed_part(creature, part, action, time, eye_open=False):
    """Independent forward kinematics, in GEO pixels with -Z facing the target."""
    model = bones(ASSETS / "geo" / f"{creature}.geo.json")
    animation = read(ASSETS / "animations" / f"{creature}.animation.json")
    tracks = animation["animations"][f"animation.{creature}.{action}"]["bones"]
    exposed = {"root", "pelvis", "torso", "chest", "tyrant_eye"} if creature == "tyrant" else {
        "root", "pelvis", "torso", "chest", "right_shoulder", "eye_open"}
    frozen = exposed if eye_open else set()
    bone = model[part]
    points = [p for cube in bone["cubes"] for p in vertices(cube)]
    while bone:
        state = {} if bone["name"] in frozen else tracks.get(bone["name"], {})
        rx, ry, rz = sample(state.get("rotation"), time, [0, 0, 0])
        # Return renderer-reflected X to GEO space after Bedrock rotation signs.
        rx, ry, rz = map(math.radians, (-rx, ry, -rz))
        scale = sample(state.get("scale"), time, [1, 1, 1])
        offset = sample(state.get("position"), time, [0, 0, 0])
        pivot = bone["pivot"]
        transformed = []
        for point in points:
            x, y, z = [(v - p) * s for v, p, s in zip(point, pivot, scale)]
            y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
            x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
            x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
            transformed.append([v + p + o for v, p, o in zip((x, y, z), pivot, offset)])
        points = transformed
        bone = model.get(bone.get("parent"))
    return points


def center(points):
    return [(min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)]


class ApprovedModelIntegrationTests(unittest.TestCase):
    def test_approved_source_is_unchanged(self):
        for creature, digest in HASHES.items():
            with self.subTest(creature=creature):
                self.assertEqual(hashlib.sha256((APPROVED / f"{creature}.geo.json").read_bytes()).hexdigest(), digest)

    def test_every_approved_cube_is_preserved_after_facing_normalization(self):
        for creature in HASHES:
            source = bones(APPROVED / f"{creature}.geo.json")
            runtime = bones(ASSETS / "geo" / f"{creature}.geo.json")
            for name, bone in source.items():
                if name == "root":
                    continue
                with self.subTest(creature=creature, part=name):
                    actual = runtime["part_" + name]
                    self.assertEqual(len(actual["cubes"]), len(bone["cubes"]))
                    self.assertEqual(actual.get("rotation", [0, 0, 0]), [0, 0, 0])
                    for before, after in zip(bone["cubes"], actual["cubes"]):
                        self.assertEqual(before["uv"], after["uv"])
                        expected_cube = copy.deepcopy(before)
                        scale = (1, 64.0 / 53.599998, 1) if creature == "tyrant" else (1, 1, 1)
                        x, y, z = before["origin"]
                        sx, sy, sz = before["size"]
                        expected_cube["origin"] = [-x - sx, y * scale[1], -z - sz]
                        expected_cube["size"] = [sx, sy * scale[1], sz]
                        if "pivot" in before:
                            px, py, pz = before["pivot"]
                            expected_cube["pivot"] = [-px, py * scale[1], -pz]
                        if "rotation" in before:
                            rx, ry, rz = before["rotation"]
                            expected_cube["rotation"] = [-rx, ry, -rz]
                        for expected in vertices(expected_cube):
                            self.assertLess(min(math.dist(expected, p) for p in vertices(after)), 1e-6)

    def test_original_palette_and_embedded_editor_texture_match(self):
        for creature in HASHES:
            palette = (APPROVED / f"{creature}_palette.png").read_bytes()
            self.assertEqual((ASSETS / "textures/entity" / f"{creature}.png").read_bytes(), palette)
            project = read(ROOT / "art" / f"{creature}.bbmodel")
            self.assertEqual(base64.b64decode(project["textures"][0]["source"].split(",", 1)[1]), palette)

    def test_runtime_textures_are_byte_distinct(self):
        digests = {}
        for creature in HASHES:
            data = (ASSETS / "textures/entity" / f"{creature}.png").read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), creature)
            digests[creature] = hashlib.sha256(data).hexdigest()
        self.assertEqual(len(set(digests.values())), 3, digests)

    def test_original_parts_have_no_implicit_pose_or_scale(self):
        for creature in HASHES:
            runtime = bones(ASSETS / "geo" / f"{creature}.geo.json")
            for name, bone in runtime.items():
                self.assertEqual(bone.get("rotation", [0, 0, 0]), [0, 0, 0], name)
                self.assertEqual(bone.get("scale", [1, 1, 1]), [1, 1, 1], name)

    def test_phase_meshes_are_separate_and_limb_bindings_are_live(self):
        t = bones(ASSETS / "geo/tyrant.geo.json")
        self.assertEqual(t["part_split_coat_tail_-1"]["parent"], "coat_intact")
        self.assertEqual(t["torn_part_split_coat_tail_-1"]["parent"], "coat_torn")
        self.assertEqual(t["part_fist_-1"]["parent"], "hand_r")
        g = bones(ASSETS / "geo/g1_birkin.geo.json")
        self.assertEqual(g["part_eye_pupil"]["parent"], "eye_open")
        self.assertEqual(g["closed_part_eye_pupil"]["parent"], "eye_closed")
        self.assertEqual(g["part_mutation_palm"]["parent"], "right_hand")
        l = bones(ASSETS / "geo/licker.geo.json")
        self.assertEqual(l["tongue_base"]["parent"], "head")
        self.assertEqual(l["part_front_hand_-1"]["parent"], "claw_r")
        self.assertEqual(l["part_rear_foot_1"]["parent"], "foot_l")
        java = (ROOT / "src/main/java/com/zeropointsix/redemo/client/CreatureModel.java").read_text()
        self.assertIn("bone.setChildrenHidden(hidden)", java)

    def test_hitbox_center_matches_visible_eye_geometry(self):
        runtime = bones(ASSETS / "geo/g1_birkin.geo.json")
        points = [[x, y, -z] for bone in runtime.values() if bone.get("parent") == "eye_open"
                  for cube in bone.get("cubes", []) for x, y, z in vertices(cube)]
        center = [(min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)]
        java = (ROOT / "src/main/java/com/zeropointsix/redemo/entity/G1BirkinEntity.java").read_text()
        declaration = re.search(r"EYE_LOCAL_CENTER = new Vec3\(([^;]+)\);", java).group(1)
        configured = [float(v.strip().split("/")[0]) for v in declaration.split(",")]
        self.assertLess(math.dist(configured, center), 0.0001)
        exposure = re.search(r"EXPOSURE_BONES = \{ ([^}]+) \}", java).group(1)
        frozen = set(re.findall(r'"([^"]+)"', exposure))
        parent = "eye_open"
        while parent:
            self.assertIn(parent, frozen)
            parent = runtime[parent].get("parent")

    def test_editor_keyframes_match_bedrock_animation_export(self):
        # Blockbench 4.12.6 compileBedrockKeyframe returns data_points unchanged.
        # Its preview renderer, not the serialized keyframe, handles reflected axes.
        for creature in HASHES:
            runtime = read(ASSETS / "animations" / f"{creature}.animation.json")["animations"]
            project = read(ROOT / "art" / f"{creature}.bbmodel")
            self.assertEqual({a["name"] for a in project["animations"]}, set(runtime))
            for animation in project["animations"]:
                exported = runtime[animation["name"]]
                self.assertEqual(animation["length"], exported["animation_length"])
                for animator in animation["animators"].values():
                    tracks = exported["bones"][animator["name"]]
                    expected = {(channel, float(time)): value for channel, samples in tracks.items()
                                for time, value in samples.items()}
                    actual = {(key["channel"], key["time"]): [key["data_points"][0][axis] for axis in "xyz"]
                              for key in animator["keyframes"]}
                    self.assertEqual(actual, expected)

    def test_manifest_runtime_hashes_match(self):
        report = read(ROOT / "art/runtime_remodel_manifest.json")
        self.assertEqual(report["source_commit"], "d28b9bdd7abd56b8aadaf47fc7414212fd2eb181")
        for creature, stats in report["creatures"].items():
            data = (ASSETS / "geo" / f"{creature}.geo.json").read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), stats["runtime_geometry_sha256"])

    def test_tyrant_fist_reaches_forward_at_damage_tick(self):
        windup = center(posed_part("tyrant", "part_fist_-1", "punch", .5))
        impact = center(posed_part("tyrant", "part_fist_-1", "punch", 16 / 20))
        self.assertLess(impact[2], -18)
        self.assertLess(impact[2], windup[2] - 15)
        self.assertTrue(25 < impact[1] < 48)
        for action, time in (("shove", .5), ("break", .7)):
            self.assertLess(center(posed_part("tyrant", "part_fist_-1", action, time))[2], -10)

    def test_charge_leans_head_and_hat_toward_travel(self):
        for part in ("part_head", "part_hat_brim"):
            self.assertLess(center(posed_part("tyrant", part, "charge", 1.55))[2], -7)

    def test_tyrant_normal_height_is_four_blocks_without_widening(self):
        model = bones(ASSETS / "geo/tyrant.geo.json")
        points = [p for name, bone in model.items() if name.startswith("part_")
                  for cube in bone.get("cubes", []) for p in vertices(cube)]
        height = max(p[1] for p in points) - min(p[1] for p in points)
        self.assertAlmostEqual(height / 16, 4, delta=.03)
        self.assertLess((max(p[0] for p in points) - min(p[0] for p in points)) / height, .7)

    def test_tyrant_eye_matches_hitbox_and_stays_aligned_during_rage_actions(self):
        model = bones(ASSETS / "geo/tyrant.geo.json")
        points = [p for cube in model["tyrant_eye"]["cubes"] for p in vertices(cube)]
        actual = center(points)
        java = (ROOT / "src/main/java/com/zeropointsix/redemo/entity/TyrantEntity.java").read_text()
        declaration = re.search(r"EYE_LOCAL_CENTER = new Vec3\(([^;]+)\);", java).group(1)
        expected = [float(v.strip().split("/")[0]) for v in declaration.split(",")]
        self.assertLess(math.dist([actual[0], actual[1], -actual[2]], expected), .0001)
        self.assertLess(actual[0], 0, "The weak eye must be on the Tyrant's right shoulder")
        self.assertEqual(model["tyrant_eye"]["parent"], "chest")
        for action in ("idle", "walk", "rage", "charge", "slash", "slash_left"):
            for time in (0, .3, .5, .8, 1):
                posed = posed_part("tyrant", "tyrant_eye", action, time, True)
                self.assertLess(math.dist(center(posed), actual), .0001, (action, time))

    def test_tyrant_left_and_right_attacks_have_mirrored_contact_poses(self):
        for action, time in (("punch", .8), ("shove", .5), ("slash", .5)):
            part = "blade_r" if action == "slash" else "part_fist_-1"
            opposite = "blade_l" if action == "slash" else "part_fist_1"
            right = center(posed_part("tyrant", part, action, time, action == "slash"))
            left = center(posed_part("tyrant", opposite, action + "_left", time, action == "slash"))
            self.assertLess(math.dist([-right[0], right[1], right[2]], left), .001, action)
            self.assertLess(right[2], -10, action)

    def test_tyrant_phase_meshes_follow_their_attacking_limbs(self):
        model = bones(ASSETS / "geo/tyrant.geo.json")
        for side in ("r", "l"):
            self.assertEqual(model["blade_" + side]["parent"], "hand_" + side)
            self.assertEqual(model["mutant_upper_" + side]["parent"], "upper_arm_" + side)
            self.assertEqual(model["mutant_forearm_" + side]["parent"], "forearm_" + side)
            action = "slash" if side == "r" else "slash_left"
            windup = center(posed_part("tyrant", "blade_" + side, action, .3, True))
            impact = center(posed_part("tyrant", "blade_" + side, action, .5, True))
            self.assertLess(impact[2], windup[2] - 15)

    def test_tyrant_eye_is_connected_to_the_chest_by_shoulder_tissue(self):
        model = bones(ASSETS / "geo/tyrant.geo.json")
        self.assertEqual(model["mutant_shoulder"]["parent"], "chest")

        def bounds(name):
            points = [p for cube in model[name]["cubes"] for p in vertices(cube)]
            return [(min(p[i] for p in points), max(p[i] for p in points)) for i in range(3)]

        mount = bounds("mutant_shoulder")
        for part in ("mutant_chest", "tyrant_eye"):
            self.assertTrue(all(min(a[1], b[1]) > max(a[0], b[0]) for a, b in zip(mount, bounds(part))),
                            "Exposed eye must visibly connect to the body, not float beside it")

    def test_tyrant_charge_has_no_render_only_displacement(self):
        animations = read(ASSETS / "animations/tyrant.animation.json")["animations"]
        self.assertEqual(animations["animation.tyrant.walk"]["animation_length"], .9)
        positions = animations["animation.tyrant.charge"]["bones"]["root"]["position"]
        self.assertTrue(all(value == [0, 0, 0] for value in positions.values()))

    def test_giant_arm_slam_descends_forward_without_eye_pose_snap(self):
        for exposed in (False, True):
            windup = center(posed_part("g1_birkin", "part_mutation_palm", "slam", .55, exposed))
            impact = center(posed_part("g1_birkin", "part_mutation_palm", "slam", 18 / 20, exposed))
            self.assertGreater(windup[1], 45)
            self.assertTrue(5 < impact[1] < 25)
            self.assertLess(impact[2], -12)
        for action, time in (("slam", .9), ("sweep", 1), ("grab", .75)):
            normal = posed_part("g1_birkin", "part_mutation_palm", action, time)
            exposed = posed_part("g1_birkin", "part_mutation_palm", action, time, True)
            for a, b in zip(normal, exposed):
                self.assertLess(math.dist(a, b), 1e-6)

    def test_giant_arm_sweeps_across_front_and_reaches_for_grab(self):
        windup = center(posed_part("g1_birkin", "part_mutation_palm", "sweep", .65, True))
        impact = center(posed_part("g1_birkin", "part_mutation_palm", "sweep", 20 / 20, True))
        follow = center(posed_part("g1_birkin", "part_mutation_palm", "sweep", 1.45, True))
        self.assertGreater(windup[0], 25)
        self.assertLess(abs(impact[0]), 2)
        self.assertLess(impact[2], -12)
        self.assertLess(follow[0], -2)
        grab = center(posed_part("g1_birkin", "part_mutation_palm", "grab", 15 / 20, True))
        self.assertLess(grab[2], -15)
        self.assertTrue(15 < grab[1] < 30)

    def test_licker_claw_strikes_ahead_and_tongue_stays_above_floor(self):
        claw = center(posed_part("licker", "part_front_hand_1", "claw", 9 / 20))
        self.assertLess(claw[2], -24)
        self.assertTrue(5 < claw[1] < 20)
        tongue = posed_part("licker", "part_tongue_4", "tongue", 11 / 20)
        rest = center(posed_part("licker", "part_tongue_4", "tongue", 0))
        self.assertLess(center(tongue)[2], rest[2] - 25)
        self.assertGreater(min(p[1] for p in tongue), 1)


if __name__ == "__main__":
    unittest.main()
