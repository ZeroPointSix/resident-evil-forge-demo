"""Guard animation contact timing and the unchanged health/base-hit budget."""

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CombatContractTests(unittest.TestCase):
    def constant(self, name):
        source = (ROOT / "src/main/java/com/zeropointsix/redemo/config/CommonConfig.java").read_text()
        return float(re.search(r"\b" + name + r"\s*=\s*([\d.]+);", source).group(1))

    def test_tongue_contact_matches_server_model_frame(self):
        path = ROOT / "src/main/resources/assets/re_demo/animations/licker.animation.json"
        bones = json.loads(path.read_text())["animations"]["animation.licker.tongue"]["bones"]
        time = self.constant("LICKER_TONGUE_HIT_FRAME") / 20
        positions = bones["tongue_base"]["position"]
        scales = bones["tongue_base"]["scale"]
        self.assertEqual(float(min(positions, key=lambda key: positions[key][2])), time)
        self.assertEqual(float(max(scales, key=lambda key: scales[key][2])), time)
        for part in ("tongue_mid", "tongue_tip"):
            self.assertIn(str(time), bones[part]["rotation"])

    def test_pressure_changes_do_not_inflate_health_or_base_hit_damage(self):
        unchanged = {
            "LICKER_HEALTH": 120, "TYRANT_HEALTH": 400, "BIRKIN_HEALTH": 480,
            "LICKER_CLAW_DAMAGE": 10, "LICKER_LEAP_DAMAGE": 14,
            "LICKER_TONGUE_DAMAGE": 8, "LICKER_AMBUSH_DAMAGE": 14,
            "TYRANT_PUNCH_DAMAGE": 16, "TYRANT_SHOVE_DAMAGE": 10,
            "TYRANT_CHARGE_DAMAGE": 22, "G1_SLAM_DAMAGE": 14,
            "G1_SWEEP_DAMAGE": 18, "G1_GRAB_DAMAGE": 6, "G1_GRAB_THROW_DAMAGE": 8,
        }
        for name, value in unchanged.items():
            with self.subTest(parameter=name):
                self.assertEqual(self.constant(name), value)


if __name__ == "__main__":
    unittest.main()
