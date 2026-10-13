"""Opt-in native CLI contracts; never touch a user's real profile."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


from scripts.distribution_contract import version
from scripts.verify_installations import commands, git_fixture, profile_env, run_command


class GitFixtureContractTests(unittest.TestCase):
    def test_catalog_can_be_available_without_its_plugin_ref(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            with git_fixture(workspace, missing_plugin_ref=True) as source:
                env = profile_env(workspace / "probe-profile")
                available = subprocess.run(["git", "ls-remote", "--exit-code", source, "refs/heads/main"],
                                           env=env, capture_output=True, text=True, timeout=30)
                missing = subprocess.run(["git", "ls-remote", "--exit-code", source, "refs/heads/stable"],
                                         env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(0, available.returncode, available.stderr)
                self.assertEqual(2, missing.returncode, missing.stderr)
                for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
                    catalog = json.loads((workspace / "git-fixture/checkout" / relative).read_text())
                    self.assertEqual("esra-agents-edge", catalog["name"])
                    self.assertEqual("stable", catalog["plugins"][0]["source"]["ref"])

    def test_codex_discovery_requires_installed_and_enabled(self):
        command = ["codex", "plugin", "list", "--json"]
        for installed, enabled in ((True, True), (False, True), (True, False)):
            with self.subTest(installed=installed, enabled=enabled):
                payload = {"installed": [{"name": "esra-agents", "version": version(),
                                          "pluginId": "esra-agents@esra-agents-edge",
                                          "marketplaceName": "esra-agents-edge",
                                          "installed": installed, "enabled": enabled}]}
                result = subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
                with patch("scripts.verify_installations.subprocess.run", return_value=result):
                    status, detail = run_command(command, {}, ROOT)
                self.assertEqual("PASS" if installed and enabled else "FAIL", status)
                if status == "FAIL":
                    self.assertIn("installation state", detail)
                    self.assertNotIn("skills/hooks", detail)

    def test_git_commands_use_edge_marketplace_identity(self):
        for host in ("codex", "claude"):
            steps = commands(host, host, Path("/unused/plugins/esra-agents"), install=True,
                             source="https://example.invalid/esra-agents.git")
            identities = [part for step in steps for part in step if part.startswith("esra-agents@")]
            self.assertTrue(identities)
            self.assertEqual({"esra-agents@esra-agents-edge"}, set(identities))
            overridden = commands(host, host, Path("/unused/plugins/esra-agents"), install=True,
                                  source="https://example.invalid/esra-agents.git", marketplace_name="esra-agents-immutable")
            self.assertTrue(any("esra-agents@esra-agents-immutable" in step for step in overridden))


@unittest.skipUnless(os.environ.get("ESRA_HOST_INTEGRATIONS") == "1", "set ESRA_HOST_INTEGRATIONS=1 for isolated native CLI tests")
class NativeInstallationTests(unittest.TestCase):
    def smoke(self, host, *, fixture=False, pin=False, missing_ref=False):
        cli = os.environ.get("ESRA_HERMES_CLI") if host == "hermes" else shutil.which("agy" if host == "antigravity" else host)
        if not cli:
            self.skipTest(f"{host} CLI unavailable (Hermes requires ESRA_HERMES_CLI prepared entry point)")
        command = [sys.executable, str(ROOT / "scripts/verify_installations.py"), "--host", host, "--install"]
        if fixture:
            command.append("--git-fixture")
        if host == "hermes":
            command.extend(["--hermes-cli", cli, "--trust-source"])
        if missing_ref:
            command.append("--missing-plugin-ref")
        if pin:
            command.append("--pin-fixture")
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        if f"SKIPPED {host}:" in result.stdout:
            self.skipTest(result.stdout.strip())

    def test_codex_tracked_git_marketplace(self):
        self.smoke("codex", fixture=True)

    def test_codex_catalog_available_but_plugin_ref_missing(self):
        self.smoke("codex", fixture=True, missing_ref=True)

    def test_claude_tracked_git_plugin(self):
        self.smoke("claude", fixture=True)

    def test_grok_tracked_git_skills_and_hooks(self):
        self.smoke("grok", fixture=True)

    def test_hermes_managed_git_source(self):
        self.smoke("hermes", fixture=True)

    def test_hermes_exact_commit_remains_pinned(self):
        self.smoke("hermes", fixture=True, pin=True)

    def test_openclaw_package_runtime_registration(self):
        self.smoke("openclaw")

    def test_antigravity_native_staged_install(self):
        self.smoke("antigravity")


if __name__ == "__main__":
    unittest.main()
