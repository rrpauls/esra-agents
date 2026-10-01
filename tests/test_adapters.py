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

    def test_hermes_adapter_declares_native_hooks(self):
        adapter = json.loads((ROOT / "adapters/hermes/adapter.json").read_text())
        self.assertTrue(adapter["native_lifecycle_hook"])
        self.assertEqual(
            {"post_tool_call", "post_llm_call", "on_session_end", "on_skill_lifecycle"},
            set(adapter["hooks"]),
        )


    def test_antigravity_root_hooks_are_valid_format(self):
        """Root hooks.json must be valid Antigravity lifecycle hooks."""
        hooks = json.loads((ROOT / "hooks.json").read_text())
        self.assertIn("esra-lifecycle", hooks)
        lifecycle = hooks["esra-lifecycle"]
        self.assertIn("PreInvocation", lifecycle)
        self.assertIn("Stop", lifecycle)
        for event in ("PreInvocation", "Stop"):
            handlers = lifecycle[event]
            self.assertIsInstance(handlers, list)
            self.assertTrue(len(handlers) > 0)
            for handler in handlers:
                self.assertEqual("command", handler.get("type", "command"))
                self.assertIn("esra_hook.py", handler["command"])
                self.assertIn("--host antigravity", handler["command"])

    def test_claude_root_hooks_are_valid_format(self):
        """Root hooks/hooks.json must be valid Claude Code hooks."""
        data = json.loads((ROOT / "hooks/hooks.json").read_text())
        self.assertIn("hooks", data)
        hooks = data["hooks"]
        for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
            self.assertIn(event, hooks)
            groups = hooks[event]
            self.assertIsInstance(groups, list)
            for group in groups:
                self.assertIn("hooks", group)
                for handler in group["hooks"]:
                    self.assertIn("esra_hook.py", handler["command"])
                    self.assertIn("--host claude", handler["command"])

    def test_openai_hooks_referenced_in_plugin_json(self):
        """OpenAI hooks path in plugin.json must resolve to an existing file."""
        plugin = json.loads((ROOT / "plugin.json").read_text())
        hook_ref = plugin["extensions"]["com.openai"]["hooks"]
        hook_path = ROOT / hook_ref.removeprefix("./")
        self.assertTrue(hook_path.is_file(), f"hook ref {hook_ref} does not resolve")
        hooks = json.loads(hook_path.read_text())
        self.assertIn("hooks", hooks)


if __name__ == "__main__":
    unittest.main()
