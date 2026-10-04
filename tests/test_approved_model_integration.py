"""Independent, dependency-free checks against the approved art baseline."""

import base64
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
                        for x, y, z in vertices(before):
                            expected = [-x, y, -z]
                            self.assertLess(min(math.dist(expected, p) for p in vertices(after)), 1e-6)

    def test_original_palette_and_embedded_editor_texture_match(self):
        for creature in HASHES:
            palette = (APPROVED / f"{creature}_palette.png").read_bytes()
            self.assertEqual((ASSETS / "textures/entity" / f"{creature}.png").read_bytes(), palette)
            project = read(ROOT / "art" / f"{creature}.bbmodel")
            self.assertEqual(base64.b64decode(project["textures"][0]["source"].split(",", 1)[1]), palette)

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


if __name__ == "__main__":
    unittest.main()
