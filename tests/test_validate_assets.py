"""Offline regression tests for the static asset acceptance gate."""

import base64
import binascii
import copy
import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "tools/qa/validate_assets.py"
SPEC = importlib.util.spec_from_file_location("asset_validator", MODULE)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def png(width=64, height=64):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    pixels = (b"\0" + b"\xff\x40\x40\xff" * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


def fixtures(creature="licker"):
    names = ["root", *validator.CONTRACTS[creature]["bones"]]
    cube = {"origin": [0, 0, 0], "size": [1, 1, 1], "uv": [0, 0]}
    bones = [{"name": name, "pivot": [0, 0, 0], "cubes": [copy.deepcopy(cube) for _ in range(20)] if i == 0 else []}
             for i, name in enumerate(names)]
    model = {"format_version": "1.12.0", "minecraft:geometry": [{
        "description": {"identifier": f"geometry.{creature}", "texture_width": 64, "texture_height": 64},
        "bones": bones,
    }]}
    animations = {"format_version": "1.8.0", "animations": {}}
    for action in (*validator.COMMON, *validator.CONTRACTS[creature]["attacks"]):
        animations["animations"][f"animation.{creature}.{action}"] = {
            "animation_length": 2.0,
            "loop": action in ("idle", "walk"),
            "bones": {"root": {"rotation": {"0": [0, 0, 0], "1": [10, 0, 0], "2": [0, 0, 0]}}},
        }
    elements = [{"uuid": f"cube-{i}", "from": [0, 0, 0], "to": [1, 1, 1]} for i in range(20)]
    source = {
        "meta": {"format_version": "4.10", "model_format": "geckolib_model"},
        "elements": elements,
        "outliner": [{"name": name, "children": [e["uuid"] for e in elements] if i == 0 else []} for i, name in enumerate(names)],
        "textures": [{"source": "data:image/png;base64," + base64.b64encode(png()).decode()}],
    }
    return model, animations, source


class AssetValidationTests(unittest.TestCase):
    def test_valid_png(self):
        self.assertEqual(validator.png_size(png()), (64, 64))

    def test_corrupt_png(self):
        data = bytearray(png())
        data[40] ^= 1
        with self.assertRaisesRegex(validator.InvalidAsset, "CRC"):
            validator.png_size(bytes(data))

    def test_truncated_png(self):
        with self.assertRaises(validator.InvalidAsset):
            validator.png_size(png()[:-8])

    def test_trailing_png_bytes(self):
        with self.assertRaises(validator.InvalidAsset):
            validator.png_size(png() + b"junk")

    def test_duplicate_json(self):
        with self.assertRaisesRegex(validator.InvalidAsset, "duplicate"):
            validator.load_json(b'{"bones":[],"bones":[]}')

    def test_non_finite_numbers(self):
        self.assertFalse(validator.vector([0, float("nan"), 0]))
        self.assertFalse(validator.number(True))
        self.assertFalse(validator.number(10**10000))

    def test_deep_json_is_reportable(self):
        with self.assertRaises(validator.InvalidAsset):
            validator.load_json(b'{"data":' + b'[' * 12000 + b'0' + b']' * 12000 + b'}')

    def test_invalid_face_uv(self):
        for uv in ({"no_face": "bad"}, {"north": "bad"}, {"north": {"uv": [0, 0], "uv_size": [65, 1]}}):
            with self.subTest(uv=uv), self.assertRaises(validator.InvalidAsset):
                validator.validate_uv(uv, (64, 64))

    def test_mirrored_face_uv_is_valid(self):
        validator.validate_uv({"north": {"uv": [20, 20], "uv_size": [-5, 5]}}, (64, 64))

    def test_dynamic_detection_ignores_metadata_and_numeric_representation(self):
        self.assertFalse(validator.dynamic_track({"0": [0, 0, 0], "1": [0.0, 0, 0]}, 2))
        self.assertFalse(validator.dynamic_track({
            "0": {"post": [0, 0, 0], "lerp_mode": "linear"},
            "1": {"post": [0, 0, 0], "lerp_mode": "catmullrom"},
        }, 2))

    def test_molang_in_single_keyframe_is_dynamic(self):
        self.assertTrue(validator.dynamic_track({"0": {"post": ["query.anim_time", 0, 0]}}, 2))

    def test_invalid_palette(self):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)

        header = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 3, 0, 0, 0))
        pixels = chunk(b"IDAT", zlib.compress(b"\0\0"))
        end = chunk(b"IEND", b"")
        for data in (header + chunk(b"PLTE", b"") + pixels + end,
                     header + pixels + chunk(b"PLTE", b"\xff\0\0") + end):
            with self.assertRaises(validator.InvalidAsset):
                validator.png_size(data)

    def test_all_three_contracts(self):
        for creature in validator.CONTRACTS:
            with self.subTest(creature=creature):
                model, animations, source = fixtures(creature)
                names = validator.validate_geometry(model, (64, 64), creature)
                validator.validate_animations(animations, names, creature)
                validator.validate_blockbench(source, names, (64, 64))

    def test_missing_state_bone(self):
        model, _, _ = fixtures("tyrant")
        model["minecraft:geometry"][0]["bones"].pop()
        with self.assertRaisesRegex(validator.InvalidAsset, "visual-state"):
            validator.validate_geometry(model, (64, 64), "tyrant")

    def test_bone_cycle(self):
        model, _, _ = fixtures()
        model["minecraft:geometry"][0]["bones"][0]["parent"] = "root"
        with self.assertRaisesRegex(validator.InvalidAsset, "cyclic"):
            validator.validate_geometry(model, (64, 64), "licker")

    def test_unknown_parent(self):
        model, _, _ = fixtures()
        model["minecraft:geometry"][0]["bones"][0]["parent"] = "missing"
        with self.assertRaisesRegex(validator.InvalidAsset, "unknown parent"):
            validator.validate_geometry(model, (64, 64), "licker")

    def test_texture_dimensions(self):
        model, _, _ = fixtures()
        with self.assertRaisesRegex(validator.InvalidAsset, "dimensions differ"):
            validator.validate_geometry(model, (32, 32), "licker")

    def test_empty_animation_is_rejected(self):
        _, animations, _ = fixtures()
        animations["animations"]["animation.licker.death"]["bones"] = {}
        with self.assertRaisesRegex(validator.InvalidAsset, "no animated bones"):
            validator.validate_animations(animations, {"root"}, "licker")

    def test_static_animation_is_rejected(self):
        _, animations, _ = fixtures()
        animations["animations"]["animation.licker.claw"]["bones"] = {"root": {"rotation": [0, 0, 0]}}
        with self.assertRaisesRegex(validator.InvalidAsset, "no changing transforms"):
            validator.validate_animations(animations, {"root"}, "licker")

    def test_unknown_animation_bone(self):
        _, animations, _ = fixtures()
        with self.assertRaisesRegex(validator.InvalidAsset, "unknown bone"):
            validator.validate_animations(animations, {"different"}, "licker")

    def test_out_of_bounds_keyframe(self):
        with self.assertRaisesRegex(validator.InvalidAsset, "outside"):
            validator.dynamic_track({"3.0": [0, 0, 0]}, 2.0)

    def test_attack_must_not_loop(self):
        _, animations, _ = fixtures()
        animations["animations"]["animation.licker.claw"]["loop"] = True
        with self.assertRaisesRegex(validator.InvalidAsset, "must not repeat"):
            validator.validate_animations(animations, {"root"}, "licker")

    def test_short_attack(self):
        _, animations, _ = fixtures()
        animations["animations"]["animation.licker.claw"]["animation_length"] = 0.2
        with self.assertRaisesRegex(validator.InvalidAsset, "before contracted"):
            validator.validate_animations(animations, {"root"}, "licker")

    def test_source_missing_cube_reference(self):
        _, _, source = fixtures()
        source["outliner"][0]["children"].pop()
        with self.assertRaisesRegex(validator.InvalidAsset, "every cube once"):
            validator.validate_blockbench(source, {"root"}, (64, 64))

    def test_source_is_portable(self):
        _, _, source = fixtures()
        source["textures"] = [{"path": "/tmp/texture.png"}]
        with self.assertRaisesRegex(validator.InvalidAsset, "portable"):
            validator.validate_blockbench(source, {"root"}, (64, 64))

    def test_jar_and_source_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            jar = root / "test.jar"
            for creature in validator.CONTRACTS:
                model, animations, source = fixtures(creature)
                files = {
                    f"src/main/resources/assets/re_demo/geo/{creature}.geo.json": json.dumps(model).encode(),
                    f"src/main/resources/assets/re_demo/animations/{creature}.animation.json": json.dumps(animations).encode(),
                    f"src/main/resources/assets/re_demo/textures/entity/{creature}.png": png(),
                    f"art/{creature}.bbmodel": json.dumps(source).encode(),
                }
                for name, data in files.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/mods.toml", "modLoader='javafml'")
                for path in (root / "src/main/resources").rglob("*"):
                    if path.is_file():
                        archive.write(path, path.relative_to(root / "src/main/resources"))
            result = validator.validate(root, jar)
            self.assertFalse(result["errors"], result)
            self.assertFalse(result["gameplay_verified"])
            original = jar.read_bytes()
            self.assertEqual(result["jar_resource_check"], {
                "requested": True, "passed": True, "matched_resources": 9,
                "name": "test.jar", "bytes": len(original),
                "sha256": hashlib.sha256(original).hexdigest(),
            })
            bad_compression = bytearray(original)
            start = 0
            while True:
                start = bad_compression.find(b"PK\x01\x02", start)
                if start < 0:
                    break
                struct.pack_into("<H", bad_compression, start + 10, 99)
                start += 4
            jar.write_bytes(bad_compression)
            result = validator.validate(root, jar)
            self.assertEqual(len(result["errors"]), 3)
            self.assertFalse(result["jar_resource_check"]["passed"])
            self.assertEqual(result["jar_resource_check"]["sha256"], hashlib.sha256(bad_compression).hexdigest())
            jar.write_bytes(original)
            (root / "src/main/resources/assets/re_demo/textures/entity/licker.png").write_bytes(png(32, 32))
            result = validator.validate(root, jar)
            self.assertTrue(any("differs from source" in error for error in result["errors"]))
            self.assertFalse(result["jar_resource_check"]["passed"])

    def test_missing_assets_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            result = validator.validate(Path(folder))
            self.assertEqual(len(result["errors"]), 3)
            self.assertFalse(result["gameplay_verified"])
            self.assertEqual(result["jar_resource_check"], {
                "requested": False, "passed": False, "matched_resources": 0,
            })

    def test_missing_jar_is_not_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = validator.validate(root, root / "missing.jar")
            self.assertTrue(result["errors"])
            self.assertEqual(result["jar_resource_check"], {
                "requested": True, "passed": False, "matched_resources": 0,
            })

    def test_jar_without_forge_metadata_is_not_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            jar = root / "not-a-mod.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("hello.txt", "test")
            result = validator.validate(root, jar)
            self.assertTrue(any("mods.toml" in error for error in result["errors"]))
            self.assertFalse(result["jar_resource_check"]["passed"])
            self.assertEqual(result["jar_resource_check"]["sha256"], hashlib.sha256(jar.read_bytes()).hexdigest())

    def test_invalid_jar_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.jar"
            path.write_bytes(b"not a jar")
            result = validator.validate(Path(folder), path)
            self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
