import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

import mcp_evidence  # noqa: E402


class McpEvidenceTests(unittest.TestCase):
    def receipt(self):
        return {
            "provider": "github",
            "kind": "workflow-run",
            "observed_at": "2026-09-26T12:34:56+03:00",
            "subject": "rrpauls/esra-agents@abc123",
            "status": "success",
            "revision": "abc123",
            "workflow": "Validate",
            "evidence": ["tests passed", "distribution checks passed"],
            "metrics": {"checks": 2, "privacy_violations": 0},
        }

    def test_normalizes_deterministically_without_evidence_text(self):
        first = mcp_evidence.normalize_receipt(self.receipt())
        second = mcp_evidence.normalize_receipt(self.receipt())
        self.assertEqual(first, second)
        encoded = json.dumps(first)
        self.assertNotIn("tests passed", encoded)
        self.assertEqual("2026-09-26T09:34:56+00:00", first["observed_at"])
        self.assertEqual(2, len(first["evidence_hashes"]))

    def test_rejects_sensitive_fields_at_any_depth(self):
        value = self.receipt()
        value["metrics"] = {"nested": {"access_token": "do-not-store"}}
        with self.assertRaisesRegex(ValueError, "sensitive field"):
            mcp_evidence.normalize_receipt(value)

    def test_output_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "receipt.json"
            source.write_text(json.dumps(self.receipt()), encoding="utf-8")
            output.write_text("old\n", encoding="utf-8")
            output.chmod(0o644)
            self.assertEqual(0, mcp_evidence.main(["--input", str(source), "--output", str(output)]))
            self.assertEqual(0o600, stat.S_IMODE(output.stat().st_mode))


if __name__ == "__main__":
    unittest.main()
