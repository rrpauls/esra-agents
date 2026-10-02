import io
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from runtime import esra_controller, esra_export, esra_runtime, mcp_evidence
from runtime.esra_paths import secure_open
from runtime import esra_paths
from scripts import build_distributions
from scripts.validate_distributions import validate_members
from tests.test_controller import SKILL_V2, passing_evaluation


class FilesystemSecurityTests(unittest.TestCase):
    def test_portable_fallback_preserves_valid_output_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(esra_paths, "DESCRIPTOR_PATHS", False):
            root = Path(temporary)
            output = root / "nested/output"
            with os.fdopen(secure_open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC), "w") as handle:
                handle.write("safe")
            self.assertEqual("safe", output.read_text())
            link = root / "link"
            link.symlink_to(output)
            with self.assertRaises(ValueError):
                secure_open(link, os.O_WRONLY | os.O_TRUNC)
            self.assertEqual("safe", output.read_text())

    def test_outputs_reject_dangling_links_ancestors_and_hardlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            victim = outside / "victim"
            victim.write_text("preserve")
            parent = root / "parent"
            parent.symlink_to(outside, target_is_directory=True)
            dangling = root / "dangling"
            dangling.symlink_to(outside / "missing")
            hardlink = root / "hardlink"
            os.link(victim, hardlink)
            for path in (parent / "victim", parent / "new", dangling, hardlink):
                for writer in (
                    lambda p: esra_export.write_jsonl([], str(p)),
                    lambda p: mcp_evidence.write_receipt({}, str(p)),
                    lambda p: os.close(secure_open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)),
                ):
                    with self.subTest(path=path, writer=writer), self.assertRaises(ValueError):
                        writer(path)
            self.assertEqual("preserve", victim.read_text())
            self.assertFalse((outside / "new").exists())
            self.assertFalse((outside / "missing").exists())

    def test_state_directories_and_changed_skills_root_reject_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside"
            outside.mkdir()
            link = root / "link"
            link.symlink_to(outside, target_is_directory=True)
            for path in (link / "state", root / "broken"):
                if path.name == "broken":
                    path.symlink_to(outside / "missing", target_is_directory=True)
                with self.assertRaises(ValueError):
                    esra_controller.Controller(path)
                with self.assertRaises(ValueError):
                    esra_runtime.resolve_data_dir("openai", str(path))
            skills = root / "skills"
            controller = esra_controller.Controller(root / "state", skills)
            skills.rmdir()
            skills.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                controller._target({"target": "helper"})
            self.assertFalse((outside / "state").exists())

    def test_rollback_rejects_linked_snapshot_and_traversal_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skills = root / "skills"
            (skills / "helper").mkdir(parents=True)
            (skills / "helper/SKILL.md").write_text("old")
            controller = esra_controller.Controller(root / "state", skills)
            candidate = controller.propose({"candidate_id": "trial", "agent_id": "agent",
                                            "target": "helper", "surface": "skills",
                                            "files": {"SKILL.md": SKILL_V2}})
            revision = candidate["revision_hash"]
            controller.evaluate("trial", passing_evaluation(revision))
            controller.promote("trial", revision, "promote")
            snapshot = controller.state / "snapshots/trial" / revision / "skill"
            snapshot.chmod(0o700)
            (snapshot / "SKILL.md").unlink()
            victim = root / "private"
            victim.write_text("private data")
            (snapshot / "SKILL.md").symlink_to(victim)
            with self.assertRaises(ValueError):
                controller.rollback("trial", "rollback")
            self.assertEqual(SKILL_V2, (skills / "helper/SKILL.md").read_text())
            stored = controller.load_candidate("trial")
            stored["revision_hash"] = "../../outside"
            controller.save_candidate(stored)
            with self.assertRaises(ValueError):
                controller.rollback("trial", "rollback-traversal")

    def test_archive_paths_and_symlink_members_are_rejected(self):
        for name in ("../outside", "/outside", "C:/outside", "a\\..\\outside", "a/../outside", "a/./file", "a/.. /outside", "a/.../outside"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    esra_controller.safe_relative(name)
                buffer = io.BytesIO()
                with ZipFile(buffer, "w") as archive:
                    archive.writestr(name, b"payload")
                with ZipFile(buffer) as archive:
                    self.assertTrue(validate_members(archive))
        buffer = io.BytesIO()
        member = ZipInfo("link")
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        with ZipFile(buffer, "w") as archive:
            archive.writestr(member, b"../outside")
        with ZipFile(buffer) as archive:
            self.assertTrue(validate_members(archive))

    def test_packager_rejects_linked_inputs_and_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("LICENSE", "NOTICE", "INSTALL.md"):
                (root / name).write_text("text")
            skill = root / "skills/helper"
            skill.mkdir(parents=True)
            victim = root / "private"
            victim.write_text("preserve")
            (skill / "SKILL.md").symlink_to(victim)
            with patch.object(build_distributions, "ROOT", root), self.assertRaises(ValueError):
                build_distributions.build_portable_skills(root / "bundle.zip")
            output = root / "output.zip"
            output.symlink_to(victim)
            with self.assertRaises(ValueError):
                with build_distributions.output_archive(output):
                    pass
            self.assertEqual("preserve", victim.read_text())

    def test_hermes_installer_rejects_linked_destination_and_extra_source(self):
        installer = build_distributions.ROOT / "adapters/hermes/install.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            for name in ("plugin.yaml", "__init__.py", "review_wakeup.py", "esra-conformance.json", "VERSION"):
                (package / name).write_text("fixture")
            for name in ("runtime", "skills"):
                (package / name).mkdir()
            outside = root / "outside"
            outside.mkdir()
            home = root / "home"
            home.mkdir()
            (home / "plugins").symlink_to(outside, target_is_directory=True)
            env = {**os.environ, "HERMES_HOME": str(home), "ESRA_PACKAGE_ROOT": str(package)}
            result = subprocess.run(["sh", str(installer)], env=env, capture_output=True)
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((outside / "esra-agents").exists())
            (home / "plugins").unlink()
            (package / "review_wakeup.py").unlink()
            (package / "review_wakeup.py").symlink_to(package / "__init__.py")
            self.assertNotEqual(0, subprocess.run(["sh", str(installer)], env=env, capture_output=True).returncode)
            (package / "review_wakeup.py").unlink()
            (package / "review_wakeup.py").write_text("fixture")
            result = subprocess.run(["sh", str(installer)], env=env, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("fixture", (home / "plugins/esra-agents/review_wakeup.py").read_text())
            self.assertEqual("fixture", (home / "plugins/esra-agents/VERSION").read_text())


if __name__ == "__main__":
    unittest.main()
