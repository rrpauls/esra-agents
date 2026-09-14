import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

import esra_export  # noqa: E402


class ExportTests(unittest.TestCase):
    def test_deterministic_schema_shape_and_privacy(self):
        secret = "PRIVATE-RAW-PROMPT"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            record = {
                "id": "cycle-1",
                "timestamp": "2026-09-12T18:00:00Z",
                "kind": "cycle",
                "outcome": "success",
                "evidence": ["synthetic evidence"],
                "verification": "tests passed",
                "prompt": secret,
                "session_id": "raw-session",
            }
            (data / "events.jsonl").write_text(json.dumps(record) + "\n")
            one = root / "one.jsonl"
            two = root / "two.jsonl"
            for output in (one, two):
                self.assertEqual(0, esra_export.main(["--data-dir", str(data), "--output", str(output)]))
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual(0o600, stat.S_IMODE(one.stat().st_mode))
            exported = json.loads(one.read_text())
            self.assertEqual(
                {"schema_version", "protocol_version", "implementation", "id", "timestamp", "event_type", "outcome", "evidence", "payload"},
                set(exported),
            )
            self.assertEqual("integration", exported["event_type"])
            self.assertNotIn(secret, one.read_text())
            self.assertNotIn("raw-session", one.read_text())

    def test_recommended_false_is_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "events.jsonl").write_text(json.dumps({"record_type": "recommended-not-run", "recommended": False}) + "\n")
            events = esra_export.export_events(root, "esra-agents")
            self.assertEqual("trigger", events[0]["event_type"])
            self.assertEqual("not-run", events[0]["outcome"])


if __name__ == "__main__":
    unittest.main()
