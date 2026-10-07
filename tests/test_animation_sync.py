import unittest
from pathlib import Path
import tempfile

from tools.qa.capture_client_evidence import EvidenceError, log_since, validate_animation_sync


class AnimationSyncEvidenceTests(unittest.TestCase):
    def logs(self):
        clients, servers = [], []
        for asset in ("licker", "tyrant", "g1_birkin"):
            for seq in (1, 2):
                servers.append(f"RE_DEMO_SYNC_SERVER uuid={asset} asset={asset} seq={seq} attack=1 tick=6 speed=1.0")
                clients.append(
                    f"RE_DEMO_SYNC_CLIENT uuid={asset} asset={asset} seq={seq} attack=1 tick=6 "
                    "partial=0.5 speed=1.0 clip=attack length=30 bone=arm prefix=5 point=1.5 "
                    "segment=5 last=false value=0.4 first=true resumed=false state=RUNNING")
            servers.append(f"RE_DEMO_SYNC_SERVER uuid={asset} asset={asset} seq=1 attack=1 tick=11 speed=1.0")
            clients.append(
                f"RE_DEMO_SYNC_CLIENT uuid={asset} asset={asset} seq=1 attack=1 tick=11 "
                "partial=0.5 speed=1.0 clip=attack length=30 bone=arm prefix=10 point=1.5 "
                "segment=5 last=false value=0.8 first=false resumed=true state=RUNNING")
        return "\n".join(clients), "\n".join(servers)

    def test_accepts_actual_segment_samples_at_late_first_frame(self):
        result = validate_animation_sync(*self.logs())
        self.assertEqual(result["sample_count"], 9)
        self.assertEqual(len(result["late_first_frames"]), 3)
        self.assertEqual(len(result["same_attack_reentries"]), 3)

    def test_accepts_accelerated_attacks_without_weakening_frame_alignment(self):
        client, server = self.logs()
        client = client.replace("speed=1.0", "speed=1.8")
        client = client.replace("prefix=5 point=1.5", "prefix=10 point=1.7")
        client = client.replace("prefix=10 point=1.5", "prefix=20 point=0.7")
        self.assertTrue(validate_animation_sync(client, server.replace("speed=1.0", "speed=1.8"))["passed"])
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client.replace("point=1.7", "point=0.0", 1), server)

    def test_rejects_a_client_speed_not_replicated_by_the_server(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client, server.replace("speed=1.0", "speed=1.8"))

    def test_log_cursor_survives_a_large_existing_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "client.log"
            path.write_bytes(b"x" * 10_000_001)
            cursor = path.stat().st_size
            with path.open("ab") as stream:
                stream.write(b"new frame\n")
            self.assertEqual(log_since(path, cursor), "new frame\n")

    def test_rejects_animation_restart_at_zero(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client.replace("point=1.5", "point=0.0", 1), server)

    def test_rejects_missing_authoritative_frame(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client, server.replace("uuid=licker", "uuid=other"))

    def test_rejects_transition_pose(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client.replace("state=RUNNING", "state=TRANSITIONING", 1), server)

    def test_rejects_missing_late_visibility_evidence(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client.replace("first=true", "first=false"), server)

    def test_handles_geckolib_final_segment_overrun(self):
        client, server = self.logs()
        client = client.replace("prefix=5 point=1.5", "prefix=5 point=6.5")
        client = client.replace("prefix=10 point=1.5", "prefix=10 point=11.5")
        client = client.replace("segment=5", "segment=1").replace("last=false", "last=true")
        self.assertTrue(validate_animation_sync(client, server)["passed"])

    def test_rejects_missing_same_attack_reentry(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client.replace("resumed=true", "resumed=false"), server)

    def test_new_attack_does_not_count_as_reentry(self):
        client, server = self.logs()
        with self.assertRaises(EvidenceError):
            validate_animation_sync(client.replace("seq=1 attack=1 tick=11", "seq=3 attack=1 tick=11"),
                                    server.replace("seq=1 attack=1 tick=11", "seq=3 attack=1 tick=11"))


if __name__ == "__main__":
    unittest.main()
