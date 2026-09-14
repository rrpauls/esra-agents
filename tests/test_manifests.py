import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_plugin import validate  # noqa: E402


class ManifestTests(unittest.TestCase):
    def test_plugin_and_adapter_contracts(self):
        self.assertEqual([], validate())

    def test_conformance_evidence_exists(self):
        manifest = json.loads((ROOT / "esra-conformance.json").read_text())
        self.assertEqual("1.2", manifest["protocol_version"])
        for capability in manifest["capabilities"].values():
            for relative in capability["evidence"]:
                path = relative.split("#", 1)[0]
                self.assertTrue((ROOT / path).exists(), relative)


if __name__ == "__main__":
    unittest.main()
