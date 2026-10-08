"""Validate active vanilla spider aliases and preserved legacy audio provenance."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from tools.generate_licker_sounds import DURATIONS, RATE, synthesize


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/main/resources/assets/re_demo"


class LickerSoundTests(unittest.TestCase):
    def test_synthesis_is_deterministic_and_non_silent(self):
        for name, duration in DURATIONS.items():
            samples = synthesize(name, duration)
            self.assertEqual(samples, synthesize(name, duration))
            self.assertEqual(len(samples), round(RATE * duration) * 2)
            self.assertGreater(len(set(samples)), 100)

    def test_every_active_licker_event_uses_vanilla_spider_audio(self):
        events = json.loads((ASSETS / "sounds.json").read_text())
        aliases = {"hiss": "ambient", "hurt": "hurt", "death": "death", "tongue": "ambient"}
        source = (ROOT / "src/main/java/com/zeropointsix/redemo/entity/LickerEntity.java").read_text()
        for name, vanilla in aliases.items():
            self.assertEqual(events["licker_" + name]["sounds"],
                             [{"name": "minecraft:entity.spider." + vanilla, "type": "event"}])
            self.assertIn("ModSounds.LICKER_" + name.upper() + ".get()", source)

    def test_unused_legacy_audio_keeps_original_hashes(self):
        manifest = json.loads((ASSETS / "sounds/licker/provenance.json").read_text())
        self.assertEqual(manifest["license"], "MIT")
        for name in DURATIONS:
            data = (ASSETS / "sounds/licker" / (name + ".ogg")).read_bytes()
            self.assertTrue(data.startswith(b"OggS"))
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["files"][name + ".ogg"]["sha256"])

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required for decoded audio validation")
    def test_original_ogg_files_decode(self):
        for name in DURATIONS:
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(ASSETS / "sounds/licker" / (name + ".ogg")),
                            "-f", "null", "-"], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
