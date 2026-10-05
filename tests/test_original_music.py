from array import array
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


music = module("validate_music", "tools/qa/validate_music.py")
capture = module("capture_client_evidence", "tools/qa/capture_client_evidence.py")


class OriginalMusicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for path in (music.ASSETS / music.AUDIO, music.ASSETS / "sounds.json",
                     music.ASSETS / "lang/en_us.json", music.ASSETS / "lang/zh_cn.json", music.REGISTRY):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, self.root / path)

    def test_real_original_asset_decodes(self):
        report = music.validate(self.root)
        self.assertTrue(report["passed"])
        self.assertEqual(report["seconds"], 24)
        self.assertFalse(report["jar_verified"])

    def test_missing_ogg_fails(self):
        (self.root / music.ASSETS / music.AUDIO).unlink()
        with self.assertRaises(FileNotFoundError):
            music.validate(self.root)

    def test_fake_ogg_fails(self):
        (self.root / music.ASSETS / music.AUDIO).write_bytes(b"not audio")
        with self.assertRaisesRegex(ValueError, "Ogg Vorbis"):
            music.validate(self.root)

    def test_vanilla_forward_is_not_original_music(self):
        path = self.root / music.ASSETS / "sounds.json"
        sounds = json.loads(path.read_text())
        sounds["encounter_theme"]["sounds"] = [{"name": "minecraft:music.game", "type": "event"}]
        path.write_text(json.dumps(sounds))
        with self.assertRaisesRegex(ValueError, "local resource"):
            music.validate(self.root)

    def test_streaming_is_required(self):
        path = self.root / music.ASSETS / "sounds.json"
        sounds = json.loads(path.read_text())
        sounds["encounter_theme"]["sounds"][0]["stream"] = False
        path.write_text(json.dumps(sounds))
        with self.assertRaisesRegex(ValueError, "stream"):
            music.validate(self.root)

    def test_missing_subtitle_fails(self):
        path = self.root / music.ASSETS / "lang/zh_cn.json"
        path.write_text("{}")
        with self.assertRaisesRegex(ValueError, "zh_cn"):
            music.validate(self.root)

    def test_unregistered_event_fails(self):
        (self.root / music.REGISTRY).write_text("class ModSounds {}")
        with self.assertRaisesRegex(ValueError, "registration"):
            music.validate(self.root)

    def packaged(self, corrupt=False):
        path = self.root / "fixture.jar"
        with zipfile.ZipFile(path, "w") as archive:
            for relative in (music.AUDIO, Path("sounds.json"), Path("lang/en_us.json"), Path("lang/zh_cn.json")):
                data = (self.root / music.ASSETS / relative).read_bytes()
                archive.writestr(f"assets/re_demo/{relative.as_posix()}", b"stale" if corrupt and relative == music.AUDIO else data)
            archive.writestr("com/zeropointsix/redemo/registry/ModSounds.class", b"encounter_theme")
        return path

    def test_packaged_bytes_must_match(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            music.validate(self.root, self.packaged(corrupt=True))

    def test_matching_package_is_accepted(self):
        self.assertTrue(music.validate(self.root, self.packaged())["jar_verified"])


class ClientAudioTests(unittest.TestCase):
    def test_real_cue_matches_after_delay_and_gain_change(self):
        with tempfile.TemporaryDirectory() as temp:
            recording = Path(temp) / "recording.wav"
            original = ROOT / music.ASSETS / music.AUDIO
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(original), "-af",
                            "adelay=1120:all=1,volume=0.3", "-t", "8", str(recording)],
                           check=True, timeout=30)
            self.assertGreater(capture.match_music(recording, original)["envelope_correlation"], 0.99)

    def test_unrelated_non_silent_audio_fails_identity_check(self):
        with tempfile.TemporaryDirectory() as temp:
            recording = Path(temp) / "unrelated.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "sine=frequency=440:duration=8", str(recording)], check=True, timeout=30)
            with self.assertRaisesRegex(capture.EvidenceError, "does not match"):
                capture.match_music(recording, ROOT / music.ASSETS / music.AUDIO)

    def test_absent_audio_stream_fails(self):
        with patch.object(capture.subprocess, "run", return_value=Mock(stdout='{"streams":[]}')):
            with self.assertRaisesRegex(capture.EvidenceError, "No recorded"):
                capture.check_audio(Path("silent.mp4"))

    def test_silent_audio_fails(self):
        outputs = [Mock(stdout='{"streams":[{"codec_name":"aac"}]}'),
                   Mock(stdout=array("f", [0.0] * 100).tobytes())]
        with patch.object(capture.subprocess, "run", side_effect=outputs):
            with self.assertRaisesRegex(capture.EvidenceError, "Silent"):
                capture.check_audio(Path("silent.mp4"))

    def test_playback_targets_registered_event_at_camera(self):
        instance = object.__new__(capture.Capture)
        instance.command, instance.confirm = Mock(), Mock()
        instance.play_music()
        commands = [c.args[0] for c in instance.command.call_args_list]
        self.assertIn("execute at EvidenceCamera", commands[1])
        self.assertIn("playsound re_demo:encounter_theme music EvidenceCamera ~ ~ ~", commands[1])
        instance.confirm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
