"""Opt-in native CLI contracts; never touch a user's real profile."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("ESRA_HOST_INTEGRATIONS") == "1", "set ESRA_HOST_INTEGRATIONS=1 for isolated native CLI tests")
class NativeInstallationTests(unittest.TestCase):
    def smoke(self, host, *, fixture=False, pin=False):
        cli = os.environ.get("ESRA_HERMES_CLI") if host == "hermes" else shutil.which("agy" if host == "antigravity" else host)
        if not cli:
            self.skipTest(f"{host} CLI unavailable (Hermes requires ESRA_HERMES_CLI prepared entry point)")
        command = [sys.executable, str(ROOT / "scripts/verify_installations.py"), "--host", host, "--install"]
        if fixture:
            command.append("--git-fixture")
        if host == "hermes":
            command.extend(["--hermes-cli", cli, "--trust-source"])
        if pin:
            command.append("--pin-fixture")
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        if f"SKIPPED {host}:" in result.stdout:
            self.skipTest(result.stdout.strip())

    def test_codex_tracked_git_marketplace(self):
        self.smoke("codex", fixture=True)

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
