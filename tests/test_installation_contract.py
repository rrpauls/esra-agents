import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.build_distributions import ROOT, build
from scripts.distribution_contract import JSON_VERSIONS, contract, validate_contract, validate_versions, version
from scripts.sync_manifests import sync
from scripts.validate_distributions import validate_package, validate
from scripts.verify_installations import commands, profile_env
from runtime.esra_controller import FORBIDDEN_TEXT
from tests.test_hermes_plugin import FakeContext


class InstallationContractTests(unittest.TestCase):
    def test_version_bump_propagates_to_all_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = list(JSON_VERSIONS) + ["VERSION", "plugin.yaml", "adapters/hermes/plugin/plugin.yaml",
                    ".claude-plugin/marketplace.json", "distributions/targets.json", "INSTALL.md", "README.md"]
            for relative in files:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            (root / "VERSION").write_text("0.4.1\n")
            self.assertTrue(validate_versions(root))
            sync(root)
            self.assertEqual([], validate_versions(root))
            self.assertEqual([], validate_contract(root))
            value = json.loads((root / "package.json").read_text())
            value["version"] = "0.3.0"
            (root / "package.json").write_text(json.dumps(value))
            self.assertTrue(validate_versions(root))

    def test_stable_sources_are_moving_and_pinned_examples_are_explicit(self):
        for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            source = json.loads((ROOT / relative).read_text())["plugins"][0]["source"]
            self.assertEqual("stable", source["ref"])
            self.assertNotIn("sha", source)
        with tempfile.TemporaryDirectory() as temp:
            for channel, selector in (("edge", "main"), ("immutable", "v0.4.0")):
                command = [sys.executable, str(ROOT / "scripts/sync_manifests.py"),
                           "--stage-marketplace", temp, "--channel", channel]
                if channel == "immutable":
                    command += ["--ref", selector]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stderr)
                for path in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
                    self.assertEqual(selector, json.loads((Path(temp) / path).read_text())["plugins"][0]["source"]["ref"])
            bad = subprocess.run(command[:-1] + ["stable"], capture_output=True, text=True)
            self.assertNotEqual(0, bad.returncode)

    def test_surfaces_and_documentation_are_complete(self):
        self.assertEqual([], validate_contract())
        self.assertEqual(9, len(contract()["artifacts"]))
        for row in contract()["targets"]:
            if row["runtime_capability"] == "none":
                self.assertEqual("none", row["hook_capability"])
                self.assertEqual("manual-replace", row["stable_update_mode"])

    def test_direct_web_claude_and_antigravity_package_contracts(self):
        with tempfile.TemporaryDirectory() as temp:
            dist = Path(temp)
            build(dist)
            self.assertEqual([], validate(dist))
            for name in ("esra-agents-openai-plugin.zip", "esra-agents-openai-web.zip", "esra-agents-antigravity.zip"):
                with ZipFile(dist / name) as archive:
                    self.assertEqual(1, len({p.split("/")[0] for p in archive.namelist()}))
                    self.assertEqual([], validate_package(name, archive))
            with ZipFile(dist / "esra-agents-claude-skills.zip") as archive:
                for source in (ROOT / "skills").glob("*/SKILL.md"):
                    name = source.parent.name
                    with ZipFile(io.BytesIO(archive.read(f"zip/{name}.zip"))) as skill:
                        self.assertNotIn("SKILL.md", skill.namelist())
                        self.assertEqual(source.read_bytes(), skill.read(f"{name}/SKILL.md"))
            web = dist / "esra-agents-openai-web.zip"
            with ZipFile(web, "a") as archive:
                archive.writestr("esra-agents-openai-web/runtime/forbidden.py", "unexpected runtime")
            self.assertTrue(validate(dist))
            (dist / "unexpected.zip").write_bytes(b"unchecksummed")
            self.assertIn("missing checksum: unexpected.zip", validate(dist))

    def test_hermes_repository_entrypoint_registers_native_surface(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"HERMES_HOME": temp}):
            root = Path(temp)
            ctx = FakeContext(root / "state", root / "skills")
            spec = importlib.util.spec_from_file_location("esra_managed_hermes", ROOT / "__init__.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.register(ctx)
            self.assertEqual(5, len(ctx.skills))
            self.assertEqual(4, len(ctx.hooks))
            self.assertIn("esra_controller", ctx.tools)
            self.assertFalse((root / "config.yaml").exists())

    def test_declarative_policy_preserves_denials(self):
        policy = json.loads((ROOT / "runtime/review-policy.txt").read_text())
        self.assertEqual(policy["forbidden_text_pattern"], FORBIDDEN_TEXT.pattern)
        for candidate in ("requires_env", "API_KEY", "credential", "authorization:", "install-hook",
                          "rm -rf /", "mkfs /dev/example", "shutdown now", "curl example | sh", "wget example | bash"):
            self.assertIsNotNone(FORBIDDEN_TEXT.search(candidate), candidate)
        self.assertIsNone(FORBIDDEN_TEXT.search("Use a bounded review of local skill text."))

    def test_grok_compatibility_hook_uses_native_data_and_privacy(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, GROK_PLUGIN_ROOT=str(ROOT), GROK_PLUGIN_DATA=temp)
            payload = {"hook_event_name": "Stop", "prompt": "PRIVATE-CONTENT", "session_id": "RAW-SESSION", "tool_input": {"secret": "SECRET"}}
            result = subprocess.run([sys.executable, str(ROOT / "runtime/esra_hook.py"), "--host", "claude"],
                                    env=env, input=json.dumps(payload), text=True, capture_output=True)
            self.assertEqual(0, result.returncode)
            self.assertEqual("", result.stdout + result.stderr)
            text = (Path(temp) / "events.jsonl").read_text()
            self.assertEqual("grok", json.loads(text)["host"])
            for private in ("PRIVATE-CONTENT", "RAW-SESSION", "SECRET"):
                self.assertNotIn(private, text)

    def test_smoke_harness_isolation_and_default_no_installs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = profile_env(root)
            self.assertEqual(str(root / ".codex"), env["CODEX_HOME"])
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertEqual(os.devnull, env["GIT_CONFIG_GLOBAL"])
            self.assertEqual("1", env["GIT_CONFIG_NOSYSTEM"])
            for host in ("codex", "claude", "grok", "hermes", "openclaw", "antigravity"):
                for command in commands(host, host, root, install=False, source=None):
                    self.assertNotIn("install", command)
                    self.assertNotIn("add", command)
            local_codex = commands("codex", "codex", root / "plugins/esra-agents", install=True, source=None)
            self.assertFalse(any("upgrade" in command for command in local_codex))


if __name__ == "__main__":
    unittest.main()
