import unittest

from tools.qa.capture_client_evidence import EvidenceError, validate_animation_sync


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
        return "\n".join(clients), "\n".join(servers)

    def test_accepts_actual_segment_samples_at_late_first_frame(self):
        result = validate_animation_sync(*self.logs())
        self.assertEqual(result["sample_count"], 6)
        self.assertEqual(len(result["late_first_frames"]), 3)

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
        client = client.replace("point=1.5", "point=6.5").replace("segment=5", "segment=1").replace("last=false", "last=true")
        self.assertTrue(validate_animation_sync(client, server)["passed"])


if __name__ == "__main__":
    unittest.main()
