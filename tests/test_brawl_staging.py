"""Keep the normal-AI brawl opening within the existing skill ranges (20261004)."""

import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("brawl_capture", ROOT / "tools/qa/capture_client_evidence.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class BrawlStagingTests(unittest.TestCase):
    def test_licker_starts_in_claw_range_before_tyrant_charge(self):
        positions = {entity: (x, z) for entity, x, z in CAPTURE.BRAWL_POSITIONS}
        self.assertEqual(set(positions), {"tyrant", "g1_birkin", "licker"})
        self.assertGreater(math.dist(positions["licker"], positions["tyrant"]), 1)
        self.assertLessEqual(math.dist(positions["licker"], positions["tyrant"]), 2.3)
        self.assertGreaterEqual(math.dist(positions["tyrant"], positions["g1_birkin"]), 4)
        self.assertLessEqual(math.dist(positions["tyrant"], positions["g1_birkin"]), 10)
        self.assertGreater(math.dist(positions["licker"], positions["g1_birkin"]), 3.4)


if __name__ == "__main__":
    unittest.main()
