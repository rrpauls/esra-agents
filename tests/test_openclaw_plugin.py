import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OpenClawPluginTests(unittest.TestCase):
    def test_native_manifest_and_exact_hook_surface(self):
        manifest = json.loads((ROOT / "openclaw.plugin.json").read_text())
        package = json.loads((ROOT / "package.json").read_text())
        source = (ROOT / package["openclaw"]["extensions"][0]).read_text()
        self.assertEqual("esra-agents", manifest["id"])
        self.assertEqual(
            {
                "model_call_ended", "after_tool_call", "agent_end",
                "skill_proposal_evaluate", "skill_proposal_changed",
                "skill_changed", "cron_changed",
            },
            {name for name in (
                "model_call_ended", "after_tool_call", "agent_end",
                "skill_proposal_evaluate", "skill_proposal_changed",
                "skill_changed", "cron_changed",
            ) if f'api.on("{name}"' in source},
        )

    def test_observers_do_not_forward_raw_content_fields(self):
        source = (ROOT / "adapters/openclaw/src/index.ts").read_text()
        ingest_body = source.split("async function ingest", 1)[1].split("function staticFindings", 1)[0]
        for forbidden in ("messages", "params", "result", "prompt", "runId", "sessionId"):
            self.assertNotIn(forbidden, ingest_body)
        self.assertIn("consume-token", source)
        self.assertIn("revisionSha256", source)


if __name__ == "__main__":
    unittest.main()
