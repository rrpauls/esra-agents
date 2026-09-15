import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.esra_controller import Controller
from tests.test_controller import passing_evaluation

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "adapters/hermes/plugin/__init__.py"


class FakeContext:
    def __init__(self, state_dir: Path, skills_dir: Path):
        self.settings = {"state_dir": str(state_dir), "agent_id": "hermes-test"}
        self.skills_dir = skills_dir
        self.hooks = {}
        self.skills = {}
        self.commands = {}
        self.cli_commands = {}
        self.tools = {}
        self.dispatched = []

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_skill(self, name, path, *args, **kwargs):
        self.skills[name] = Path(path)

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler

    def register_cli_command(self, name, **kwargs):
        self.cli_commands[name] = kwargs

    def register_tool(self, name, handler, **kwargs):
        self.tools[name] = handler

    def dispatch_tool(self, name, args):
        self.dispatched.append((name, args))
        if name == "cronjob_manage":
            return json.dumps({"success": True, "job_id": f"cron-{len(self.dispatched)}"})
        if name != "skill_manage":
            return json.dumps({"success": False})
        for operation in args["operations"]:
            target = self.skills_dir / operation["name"]
            target.mkdir(parents=True, exist_ok=True)
            if operation["action"] in {"create", "patch"}:
                (target / "SKILL.md").write_text(operation["content"], encoding="utf-8")
            elif operation["action"] == "write_file":
                output = target / operation["file_path"]
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(operation["file_content"], encoding="utf-8")
        return json.dumps({"success": True})


def load_plugin():
    spec = importlib.util.spec_from_file_location("esra_hermes_plugin_test", PLUGIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HermesPluginTests(unittest.TestCase):
    def test_native_plugin_registers_hooks_commands_tool_and_five_skills(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"HERMES_HOME": directory}):
            root = Path(directory)
            ctx = FakeContext(root / "state", root / "skills")
            plugin = load_plugin()
            plugin.register(ctx)
            self.assertEqual(
                {"post_tool_call", "post_llm_call", "on_session_end", "on_skill_lifecycle"},
                set(ctx.hooks),
            )
            self.assertEqual(5, len(ctx.skills))
            self.assertIn("esra", ctx.commands)
            self.assertIn("esra", ctx.cli_commands)
            self.assertIn("esra_controller", ctx.tools)

    def test_hooks_never_persist_raw_hermes_content(self):
        secret = "RAW-HERMES-SECRET"
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"HERMES_HOME": directory}):
            root = Path(directory)
            ctx = FakeContext(root / "state", root / "skills")
            plugin = load_plugin()
            plugin.register(ctx)
            ctx.hooks["post_tool_call"](
                tool_name="terminal", status="error", duration_ms=12,
                error_type="CommandError", args={"password": secret}, result=secret,
                error_message=secret, session_id="raw-session",
            )
            durable = (root / "state/events.jsonl").read_text(encoding="utf-8")
            self.assertNotIn(secret, durable)
            self.assertNotIn("raw-session", durable)
            self.assertNotIn("password", durable)

    def test_apply_tool_uses_skill_manage_and_completes_exact_revision(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"HERMES_HOME": directory}):
            root = Path(directory)
            state = root / "state"
            skills = root / "skills"
            ctx = FakeContext(state, skills)
            plugin = load_plugin()
            plugin.register(ctx)
            controller = Controller(state, skills)
            candidate = controller.propose({
                "candidate_id": "hermes-candidate",
                "agent_id": "hermes-test",
                "target": "local-helper",
                "files": {"SKILL.md": "---\nname: local-helper\ndescription: Use when testing.\n---\n\nDo the local task.\n"},
            })
            controller.evaluate(
                candidate["candidate_id"],
                passing_evaluation(candidate["revision_hash"], "hermes-evaluation"),
            )
            token = controller.issue_apply_token(
                candidate["candidate_id"], candidate["revision_hash"], candidate["revision_hash"]
            )["apply_token"]
            raw = ctx.tools["esra_controller"]({
                "action": "apply", "candidate_id": candidate["candidate_id"], "apply_token": token,
            })
            result = json.loads(raw)
            self.assertTrue(result["success"])
            self.assertEqual("skill_manage", ctx.dispatched[0][0])
            self.assertEqual("active", Controller(state, skills).load_candidate(candidate["candidate_id"])["state"])

    def test_cron_install_uses_fresh_restricted_jobs_and_durable_monitor(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"HERMES_HOME": directory}):
            root = Path(directory)
            ctx = FakeContext(root / "state", root / "skills")
            plugin = load_plugin()
            result = plugin._install_cron(ctx, "0 2 * * *")
            self.assertTrue(result["nightly"]["success"])
            calls = [args for name, args in ctx.dispatched if name == "cronjob_manage"]
            self.assertEqual(2, len(calls))
            self.assertEqual(["esra", "skills"], calls[0]["enabled_toolsets"])
            self.assertNotIn("script", calls[1])
            self.assertEqual(result["wakeup_script"], calls[1]["monitor"])
            self.assertEqual(["esra-orchestrator"], calls[1]["skills"])
            self.assertTrue(Path(result["wakeup_script"]).is_file())


if __name__ == "__main__":
    unittest.main()
