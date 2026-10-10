"""Validate independent Licker resources and their installed-JAR provenance."""

import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from tools.generate_licker_sounds import DURATIONS, RATE, synthesize
from tools.qa.capture_client_evidence import Capture, EvidenceError, check_original_licker_sounds


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/main/resources/assets/re_demo"


class LickerSoundTests(unittest.TestCase):
    def test_synthesis_is_deterministic_and_non_silent(self):
        for name, duration in DURATIONS.items():
            samples = synthesize(name, duration)
            self.assertEqual(samples, synthesize(name, duration))
            self.assertEqual(len(samples), round(RATE * duration) * 2)
            self.assertGreater(len(set(samples)), 100)

    def test_every_active_licker_event_uses_original_audio(self):
        events = json.loads((ASSETS / "sounds.json").read_text())
        source = (ROOT / "src/main/java/com/zeropointsix/redemo/entity/LickerEntity.java").read_text()
        for name in DURATIONS:
            self.assertEqual(events["licker_" + name]["sounds"],
                             ["re_demo:licker/" + name])
            self.assertIn("ModSounds.LICKER_" + name.upper() + ".get()", source)

    def test_active_audio_keeps_original_hashes(self):
        manifest = json.loads((ASSETS / "sounds/licker/provenance.json").read_text())
        self.assertEqual(manifest["license"], "MIT")
        for name in DURATIONS:
            data = (ASSETS / "sounds/licker" / (name + ".ogg")).read_bytes()
            self.assertTrue(data.startswith(b"OggS"))
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["files"][name + ".ogg"]["sha256"])

    def packaged_sounds(self):
        paths = ["sounds.json", "sounds/licker/provenance.json"]
        paths += ["sounds/licker/" + name + ".ogg" for name in DURATIONS]
        return {"assets/re_demo/" + path: (ASSETS / path).read_bytes() for path in paths}

    def validate_package(self, files):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive:
            return check_original_licker_sounds(archive)

    def test_installed_jar_checks_all_four_original_resources(self):
        records = self.validate_package(self.packaged_sounds())
        self.assertEqual(set(records), set(DURATIONS))
        for name, record in records.items():
            self.assertEqual(record["resource"], "re_demo:licker/" + name)
            self.assertGreater(record["bytes"], 100)

    def test_installed_jar_rejects_spider_alias_for_each_event(self):
        for name in DURATIONS:
            with self.subTest(event=name):
                files = self.packaged_sounds()
                events = json.loads(files["assets/re_demo/sounds.json"])
                events["licker_" + name]["sounds"] = [
                    {"name": "minecraft:entity.spider.ambient", "type": "event"}]
                files["assets/re_demo/sounds.json"] = json.dumps(events).encode()
                with self.assertRaises(EvidenceError):
                    self.validate_package(files)

    def test_installed_jar_rejects_missing_corrupt_or_unproven_audio(self):
        for corruption in ("missing", "corrupt", "provenance", "malformed"):
            with self.subTest(corruption=corruption):
                files = self.packaged_sounds()
                path = "assets/re_demo/sounds/licker/tongue.ogg"
                manifest = "assets/re_demo/sounds/licker/provenance.json"
                if corruption == "missing":
                    del files[path]
                elif corruption == "corrupt":
                    files[path] += b"changed"
                elif corruption == "provenance":
                    info = json.loads(files[manifest])
                    info["license"] = "unknown"
                    files[manifest] = json.dumps(info).encode()
                else:
                    files[manifest] = b"not JSON"
                with self.assertRaises(EvidenceError):
                    self.validate_package(files)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required for decoded audio validation")
    def test_original_ogg_files_decode(self):
        for name in DURATIONS:
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(ASSETS / "sounds/licker" / (name + ".ogg")),
                            "-f", "null", "-"], check=True, capture_output=True)

    def test_client_playback_records_and_checks_each_event(self):
        capture = object.__new__(Capture)
        capture.report = {}
        capture.command, capture.confirm = Mock(), Mock()
        capture.start = Mock(return_value=Mock(wait=Mock(return_value=0)))
        with tempfile.TemporaryDirectory() as directory:
            capture.output = capture.work = Path(directory)
            with patch("tools.qa.capture_client_evidence.time.sleep"), \
                    patch("tools.qa.capture_client_evidence.file_record", return_value={}), \
                    patch("tools.qa.capture_client_evidence.check_audio", return_value={"rms": 0.02}) as audio:
                capture.verify_licker_playback()
        self.assertEqual(set(capture.report["licker_client_playback"]), set(DURATIONS))
        self.assertEqual(audio.call_count, 4)
        commands = [call.args[0] for call in capture.command.call_args_list]
        for name in DURATIONS:
            self.assertTrue(any("playsound re_demo:licker_" + name + " hostile" in cmd for cmd in commands))

    def test_client_playback_does_not_accept_silence(self):
        capture = object.__new__(Capture)
        capture.report = {}
        capture.output = capture.work = Path("unused-playback-fixture")
        capture.command, capture.confirm = Mock(), Mock()
        capture.start = Mock(return_value=Mock(wait=Mock(return_value=0)))
        with patch("tools.qa.capture_client_evidence.time.sleep"), \
                patch("tools.qa.capture_client_evidence.file_record", return_value={}), \
                patch("tools.qa.capture_client_evidence.check_audio", side_effect=EvidenceError("Silent")):
            with self.assertRaises(EvidenceError):
                capture.verify_licker_playback()
        self.assertEqual(capture.report["licker_client_playback"], {})


if __name__ == "__main__":
    unittest.main()
