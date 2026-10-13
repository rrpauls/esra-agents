"""Offline regressions for the separate published-source probe."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts.verify_published_sources import verify_source, verify_catalogs
import json


class PublishedSourceTests(unittest.TestCase):
    def test_empty_success_is_not_available(self):
        with patch("scripts.verify_published_sources.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")):
            self.assertTrue(verify_source("unused", "stable"))

    def test_catalog_available_plugin_ref_missing_and_sha_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-b", "main", temp], check=True, capture_output=True)
            for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
                path = root / relative
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({"plugins": [{"source": {"url": temp, "ref": "stable"}}]}))
            subprocess.run(["git", "add", "."], cwd=temp, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "Catalog available"], cwd=temp, check=True, capture_output=True)
            self.assertTrue(verify_catalogs(root))
            self.assertEqual([], verify_source(temp, "main"))
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=temp, text=True).strip()
            self.assertEqual([], verify_source(temp, sha))
            self.assertTrue(verify_source(temp, "f" * 40))
