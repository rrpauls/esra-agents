import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

import esra_runtime as runtime  # noqa: E402


class RuntimeTests(unittest.TestCase):
    def test_host_path_resolution_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {"HERMES_HOME": str(root)}, clear=True):
                data = runtime.resolve_data_dir("hermes")
            self.assertEqual(root / "esra/data", data)
            self.assertEqual(0o700, stat.S_IMODE(data.stat().st_mode))

    def test_record_contains_only_explicit_evidence_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            code = runtime.main([
                "--data-dir", directory,
                "record", "--task-id", "task-1", "--outcome", "success",
                "--evidence", "tests passed", "--verification", "archive extracted",
            ])
            self.assertEqual(0, code)
            record = json.loads((Path(directory) / "events.jsonl").read_text())
            self.assertEqual("task-1", record["task_id"])
            self.assertNotIn("prompt", record)
            self.assertEqual(0o600, stat.S_IMODE((Path(directory) / "events.jsonl").stat().st_mode))

    def test_trigger_is_recommendation_only_and_rate_limited(self):
        with tempfile.TemporaryDirectory() as directory:
            args = [
                "--data-dir", directory, "trigger", "--complexity", "9",
                "--major-change", "--session", "same",
            ]
            with redirect_stdout(StringIO()):
                self.assertEqual(0, runtime.main(args))
            history = json.loads((Path(directory) / "trigger-history.json").read_text())
            self.assertEqual(1, len(history))
            with redirect_stdout(StringIO()):
                self.assertEqual(0, runtime.main(args))
            history = json.loads((Path(directory) / "trigger-history.json").read_text())
            self.assertEqual(1, len(history))

    def test_alignment_gate_and_bounded_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            common = [
                "--data-dir", directory, "experiment", "create", "--id", "trial",
                "--hypothesis", "candidate remains successful",
                "--baseline-command", f"{sys.executable} -c pass",
                "--candidate-command", f"{sys.executable} -c pass",
                "--guardrail", "stop on candidate failure", "--rollback", "discard fixture",
            ]
            with redirect_stderr(StringIO()):
                self.assertEqual(1, runtime.main(common + ["--alignment", "0.2"]))
            self.assertEqual(0, runtime.main(common))
            self.assertEqual(0, runtime.main(["--data-dir", directory, "experiment", "run", "--id", "trial"]))
            record = json.loads((Path(directory) / "experiments/trial.json").read_text())
            self.assertEqual("completed", record["status"])
            self.assertTrue(
                all(
                    key.endswith("_digest")
                    for run in record["runs"]
                    for key in run
                    if key.startswith(("stdout", "stderr"))
                )
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_refuses_symlinked_data_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlinked data directory"):
                runtime.resolve_data_dir("openai", str(link))


if __name__ == "__main__":
    unittest.main()
