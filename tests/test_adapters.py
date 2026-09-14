import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def test_hooks_are_silent_and_privacy_allowlisted(self):
        secret = "PRIVATE-PROMPT-CONTENT"
        with tempfile.TemporaryDirectory() as directory:
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "raw-session-id",
                "cwd": "/tmp/synthetic-project",
                "prompt": secret,
                "transcript_path": "/private/transcript.jsonl",
                "tool_input": {"token": "secret"},
            }
            process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "runtime/esra_hook.py"),
                    "--host", "claude", "--data-dir", directory,
                ],
                input=json.dumps(payload), text=True, capture_output=True, check=False,
            )
            self.assertEqual(0, process.returncode)
            self.assertEqual("", process.stdout)
            self.assertEqual("", process.stderr)
            durable = (Path(directory) / "events.jsonl").read_text()
            self.assertNotIn(secret, durable)
            self.assertNotIn("raw-session-id", durable)
            self.assertNotIn("transcript", durable)
            record = json.loads(durable)
            self.assertEqual("claude", record["host"])
            self.assertEqual("synthetic-project", record["workspace"])

    def test_malformed_hook_never_blocks(self):
        process = subprocess.run(
            [sys.executable, str(ROOT / "runtime/esra_hook.py"), "--host", "openai"],
            input="not-json", text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, process.returncode)
        self.assertEqual("", process.stdout)
        self.assertEqual("", process.stderr)

    def test_hermes_claim_is_explicitly_non_native(self):
        adapter = json.loads((ROOT / "adapters/hermes/adapter.json").read_text())
        self.assertFalse(adapter["native_lifecycle_hook"])


if __name__ == "__main__":
    unittest.main()
