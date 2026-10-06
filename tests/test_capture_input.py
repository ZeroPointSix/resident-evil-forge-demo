"""Capture input must retain modifiers and release the complete sprint chord."""

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "input_capture", ROOT / "tools/qa/capture_client_evidence.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class CaptureInputTests(unittest.TestCase):
    def setUp(self):
        self.capture = object.__new__(CAPTURE.Capture)

    def test_sneak_movement_preserves_shift(self):
        with patch.object(CAPTURE.subprocess, "run") as run:
            for name, down in (("shift", True), ("w", True),
                               ("w", False), ("shift", False)):
                self.capture.key(name, down)
        self.assertEqual(run.call_args_list, [
            call(["xdotool", "keydown", "shift"], check=True, timeout=10),
            call(["xdotool", "keydown", "w"], check=True, timeout=10),
            call(["xdotool", "keyup", "w"], check=True, timeout=10),
            call(["xdotool", "keyup", "shift"], check=True, timeout=10),
        ])

    def test_sprint_holds_control_and_w_without_clearing_modifiers(self):
        events = []
        with patch.object(CAPTURE.subprocess, "run", side_effect=lambda cmd, **kw: events.append(cmd)), \
                patch.object(CAPTURE.time, "sleep", side_effect=lambda seconds: events.append(seconds)):
            self.capture.sprint_forward()
        self.assertEqual(events, [
            ["xdotool", "keydown", "Control_L"],
            ["xdotool", "keydown", "w"],
            1.5,
            ["xdotool", "keyup", "w"],
            ["xdotool", "keyup", "Control_L"],
        ])

    def test_interrupted_hold_releases_both_keys(self):
        with patch.object(CAPTURE.subprocess, "run") as run, \
                patch.object(CAPTURE.time, "sleep", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.capture.sprint_forward()
        self.assertEqual([c.args[0] for c in run.call_args_list[-2:]], [
            ["xdotool", "keyup", "w"], ["xdotool", "keyup", "Control_L"]])

    def test_failed_w_release_still_releases_control(self):
        def fail_w_release(cmd, **kwargs):
            if cmd == ["xdotool", "keyup", "w"]:
                raise subprocess.CalledProcessError(1, cmd)

        with patch.object(CAPTURE.subprocess, "run", side_effect=fail_w_release) as run, \
                patch.object(CAPTURE.time, "sleep"):
            with self.assertRaises(subprocess.CalledProcessError):
                self.capture.sprint_forward()
        self.assertEqual(run.call_args.args[0], ["xdotool", "keyup", "Control_L"])


if __name__ == "__main__":
    unittest.main()
