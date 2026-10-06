"""Verify GeckoLib stays external, including Forge jar-in-jar packaging (20261004)."""

import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dependency_capture", ROOT / "tools/qa/capture_client_evidence.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


def archive_bytes(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class DependencyBoundaryTests(unittest.TestCase):
    def check(self, entries):
        with zipfile.ZipFile(io.BytesIO(archive_bytes(entries))) as archive:
            CAPTURE.check_external_geckolib(archive)

    def test_expanded_geckolib_rejected(self):
        with self.assertRaisesRegex(CAPTURE.EvidenceError, "must not bundle"):
            self.check({"software/bernie/geckolib/GeckoLib.class": b"fixture"})

    def test_nested_geckolib_rejected_regardless_of_filename(self):
        nested = archive_bytes({"software/bernie/geckolib/GeckoLib.class": b"fixture"})
        with self.assertRaisesRegex(CAPTURE.EvidenceError, "jar-in-jar"):
            self.check({"META-INF/jarjar/dependency.jar": nested})

    def test_external_dependency_and_unrelated_embedded_jar_allowed(self):
        self.check({"META-INF/mods.toml": b"geckolib", "assets/re_demo/example": b"resource",
                    "META-INF/jarjar/unrelated.jar": archive_bytes({"example/Helper.class": b"fixture"})})


if __name__ == "__main__":
    unittest.main()
