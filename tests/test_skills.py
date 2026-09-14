import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_skills import validate  # noqa: E402


class SkillTests(unittest.TestCase):
    def test_all_portable_skills_validate(self):
        self.assertEqual([], validate())

    def test_expected_focused_catalog(self):
        self.assertEqual(
            {
                "esra-crisis",
                "esra-decisions",
                "esra-experiments",
                "esra-orchestrator",
                "esra-reflection",
            },
            {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()},
        )

    def test_selective_invocation_and_no_recursion(self):
        orchestrator = (ROOT / "skills/esra-orchestrator/SKILL.md").read_text()
        self.assertIn("Routine answers", orchestrator)
        self.assertIn("at most one bounded review", orchestrator)
        self.assertIn("Never let an ESRA review", orchestrator)
        self.assertNotIn("must invoke all", orchestrator.lower())


if __name__ == "__main__":
    unittest.main()
