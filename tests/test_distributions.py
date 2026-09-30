import tempfile
import io
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.build_distributions import ROOT, build, build_portable_skills
from scripts.validate_distributions import check_checksums, validate, validate_portable_skills


class DistributionTests(unittest.TestCase):
    def test_portable_skills_are_directly_importable_and_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary) / "skills.zip"
            build_portable_skills(bundle)
            with ZipFile(bundle) as archive:
                self.assertEqual([], validate_portable_skills(archive))
                for name in ("esra-orchestrator", "esra-decisions", "esra-experiments", "esra-reflection", "esra-crisis"):
                    source = (ROOT / "skills" / name / "SKILL.md").read_bytes()
                    self.assertEqual(source, archive.read(f"markdown/{name}.md"))
                    with ZipFile(io.BytesIO(archive.read(f"zip/{name}.zip"))) as skill:
                        self.assertEqual({"SKILL.md", "LICENSE", "NOTICE"}, set(skill.namelist()))
                        self.assertEqual(source, skill.read("SKILL.md"))
                contents = {name: archive.read(name) for name in archive.namelist()}
            for change in ("missing", "altered", "wrong-root"):
                modified = dict(contents)
                if change == "missing":
                    del modified["zip/esra-decisions.zip"]
                elif change == "altered":
                    modified["markdown/esra-decisions.md"] = b"altered"
                else:
                    inner = io.BytesIO()
                    with ZipFile(inner, "w") as skill:
                        skill.writestr("nested/SKILL.md", b"wrong root")
                    modified["zip/esra-decisions.zip"] = inner.getvalue()
                with ZipFile(bundle, "w") as archive:
                    for name, data in modified.items():
                        archive.writestr(name, data)
                with ZipFile(bundle) as archive:
                    self.assertTrue(validate_portable_skills(archive), change)

    def test_checksums_require_complete_coverage(self):
        self.assertIn("missing checksum: skill.zip", check_checksums("", {"skill.zip": b"data"}))
        self.assertTrue(check_checksums("invalid", {}))

    def test_archives_validate_and_are_reproducible(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            outputs_one = build(Path(first))
            outputs_two = build(Path(second))
            self.assertIn("esra-agents-openai.zip", {path.name for path in outputs_one})
            self.assertNotIn("esra-agents-marketplace.zip", {path.name for path in outputs_one})
            self.assertEqual([], validate(Path(first)))
            self.assertEqual([], validate(Path(second)))
            for one, two in zip(outputs_one, outputs_two, strict=True):
                self.assertEqual(one.read_bytes(), two.read_bytes())


if __name__ == "__main__":
    unittest.main()
