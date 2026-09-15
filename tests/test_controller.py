import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from runtime.esra_controller import Controller, atomic_json, digest, now, redact_excerpts


SKILL_V1 = """---
name: helper
description: Handle routine local tasks.
---

Follow the requested local workflow.
"""
SKILL_V2 = SKILL_V1.replace("routine local tasks", "routine local tasks reliably")


def passing_evaluation(revision: str, key: str = "experiment-1") -> dict:
    return {
        "revision_hash": revision,
        "idempotency_key": key,
        "deterministic_pass": True,
        "alignment_decision": "allow",
        "blind": True,
        "proposal_context_visible": False,
        "replays": [
            {"fixture_id": "r1", "judge": "candidate", "critical_regression": False},
            {"fixture_id": "r2", "judge": "candidate", "critical_regression": False},
            {"fixture_id": "r3", "judge": "baseline", "critical_regression": False},
        ],
        "evidence_hashes": [digest("blind-results", 16)],
    }


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.skills = self.root / "skills"
        self.controller = Controller(self.state, self.skills)

    def tearDown(self):
        self.temporary.cleanup()

    def proposal(self, candidate: str = "candidate-1", target: str = "helper", agent: str = "agent-1", content: str = SKILL_V2):
        return self.controller.propose({
            "candidate_id": candidate,
            "agent_id": agent,
            "target": target,
            "surface": "skills",
            "files": {"SKILL.md": content},
            "evidence_hashes": [digest("local-evidence", 16)],
        })

    def test_event_storage_is_sanitized_and_recursive_events_are_ignored(self):
        stored = self.controller.ingest({
            "agent_id": "raw-agent-id",
            "run_id": "raw-run-id",
            "host": "openclaw",
            "event_type": "agent_end",
            "outcome": "success",
            "substantial": True,
            "prompt": "do not persist me",
        })
        self.assertNotIn("agent_id", stored)
        self.assertNotIn("run_id", stored)
        self.assertNotIn("prompt", stored)
        self.assertEqual(16, len(stored["agent_hash"]))
        self.assertTrue(self.controller.ingest({
            "agent_id": "raw-agent-id",
            "correlation_id": "esra:review-1",
            "event_type": "agent_end",
        })["ignored"])
        disk = self.controller.events_path.read_text(encoding="utf-8")
        self.assertNotIn("raw-agent-id", disk)
        self.assertNotIn("do not persist", disk)

    def test_reviewer_excerpts_are_bounded_and_redacted(self):
        secret = "top-secret-value"
        values = redact_excerpts(
            [f"token={secret} bearer abc.def", "x" * 4096, "three", "four", "five"],
            [secret],
        )
        self.assertEqual(4, len(values))
        self.assertNotIn(secret, "".join(values))
        self.assertLessEqual(len(values[1].encode()), 2048)

    def test_trigger_requires_evidence_and_is_once_per_day_after_restart(self):
        self.assertFalse(self.controller.tick("agent-1")["review"])
        for _ in range(2):
            self.controller.ingest({
                "agent_id": "agent-1",
                "host": "hermes",
                "event_type": "tool_call",
                "outcome": "failure",
                "error_class": "same-error",
            })
        first = self.controller.tick("agent-1")
        self.assertTrue(first["review"])
        restarted = Controller(self.state, self.skills)
        self.assertEqual("daily-budget", restarted.tick("agent-1")["reason"])
        claimed = restarted.next_review("agent-1")["review"]
        self.assertEqual(first["correlation_id"], claimed["correlation_id"])
        completed = restarted.complete_review(
            "agent-1", claimed["correlation_id"], "no-change", digest("review-result", 16)
        )
        self.assertEqual("completed", completed["status"])
        self.assertIsNone(restarted.next_review("agent-1")["review"])

    def test_nightly_requires_three_substantial_tasks(self):
        for number in range(3):
            self.controller.ingest({
                "agent_id": "agent-nightly",
                "host": "openclaw",
                "event_type": "agent_end",
                "outcome": "success",
                "substantial": number < 2,
            })
        self.assertFalse(self.controller.tick("agent-nightly", nightly=True)["review"])
        self.controller.ingest({
            "agent_id": "agent-nightly",
            "host": "openclaw",
            "event_type": "agent_end",
            "outcome": "success",
            "substantial": True,
        })
        self.assertTrue(self.controller.tick("agent-nightly", nightly=True)["review"])

    def test_protected_and_privileged_targets_require_human(self):
        core = self.proposal(candidate="core", target="esra-controller", content=SKILL_V2)
        self.assertTrue(core["requires_human"])
        self.assertIn("protected-core-target", core["risk_reasons"])
        networked = self.proposal(
            candidate="networked",
            target="helper-two",
            agent="agent-2",
            content=SKILL_V2 + "\nUse https://example.invalid and requires_env TOKEN.\n",
        )
        self.assertTrue(networked["requires_human"])
        self.assertIn("network-endpoint", networked["risk_reasons"])

    def test_full_state_machine_promotes_exact_revision_and_accepts_canary(self):
        target = self.skills / "helper"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(SKILL_V1, encoding="utf-8")
        candidate = self.proposal()
        evaluated = self.controller.evaluate(candidate["candidate_id"], passing_evaluation(candidate["revision_hash"]))
        self.assertEqual("evaluated", evaluated["state"])
        receipt = self.controller.promote(candidate["candidate_id"], candidate["revision_hash"], "promote-1")
        self.assertEqual("promote", receipt["action"])
        self.assertEqual(SKILL_V2, (target / "SKILL.md").read_text(encoding="utf-8"))
        for number in range(5):
            self.controller.ingest({
                "agent_id": "agent-1",
                "host": "openclaw",
                "event_type": "agent_end",
                "outcome": "success",
                "candidate_id": candidate["candidate_id"],
                "substantial": True,
                "evidence_digest": digest(number, 16),
            })
        accepted = self.controller.load_candidate(candidate["candidate_id"])
        self.assertEqual("accepted", accepted["state"])
        path = [(row["from"], row["to"]) for row in accepted["transitions"]]
        self.assertEqual(
            [("observed", "proposed"), ("proposed", "aligned"), ("aligned", "evaluated"),
             ("evaluated", "staged"), ("staged", "active"), ("active", "accepted")],
            path,
        )
        self.assertEqual(receipt, Controller(self.state, self.skills).promote(
            candidate["candidate_id"], candidate["revision_hash"], "promote-1"
        ))

    def test_bad_candidate_is_quarantined_and_tie_is_inconclusive(self):
        bad = self.proposal(candidate="bad", agent="bad-agent")
        blocked = passing_evaluation(bad["revision_hash"], "bad-eval")
        blocked["replays"][0]["critical_regression"] = True
        self.assertEqual("quarantined", self.controller.evaluate("bad", blocked)["state"])

        tie = self.proposal(candidate="tie", target="helper-tie", agent="tie-agent")
        inconclusive = passing_evaluation(tie["revision_hash"], "tie-eval")
        inconclusive["replays"][1]["judge"] = "baseline"
        self.assertEqual("inconclusive", self.controller.evaluate("tie", inconclusive)["state"])

    def test_stale_revision_and_experiment_budget_are_enforced(self):
        candidate = self.proposal(candidate="first", agent="budget-agent")
        with self.assertRaisesRegex(ValueError, "stale"):
            self.controller.evaluate("first", passing_evaluation("0" * 64))
        self.controller.evaluate("first", passing_evaluation(candidate["revision_hash"], "first-eval"))
        second = self.proposal(candidate="second", target="helper-second", agent="budget-agent")
        with self.assertRaisesRegex(ValueError, "experiment budget"):
            self.controller.evaluate("second", passing_evaluation(second["revision_hash"], "second-eval"))

    def test_apply_token_is_revision_bound_and_one_time(self):
        candidate = self.proposal()
        self.controller.evaluate("candidate-1", passing_evaluation(candidate["revision_hash"]))
        host_revision = digest("openclaw-workshop-revision")
        issued = self.controller.issue_apply_token(
            "candidate-1", candidate["revision_hash"], host_revision
        )
        with self.assertRaisesRegex(ValueError, "host revision mismatch"):
            self.controller.consume_apply_token(
                issued["apply_token"], "candidate-1", digest("stale-host-revision")
            )
        self.assertTrue(self.controller.consume_apply_token(
            issued["apply_token"], "candidate-1", host_revision
        )["authorized"])
        with self.assertRaisesRegex(ValueError, "consumed"):
            self.controller.consume_apply_token(
                issued["apply_token"], "candidate-1", host_revision
            )

    def test_canary_regression_rolls_back_snapshot(self):
        target = self.skills / "helper"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(SKILL_V1, encoding="utf-8")
        candidate = self.proposal()
        self.controller.evaluate("candidate-1", passing_evaluation(candidate["revision_hash"]))
        self.controller.promote("candidate-1", candidate["revision_hash"], "promote-rollback")
        for _ in range(2):
            self.controller.ingest({
                "agent_id": "agent-1",
                "host": "hermes",
                "event_type": "agent_end",
                "outcome": "failure",
                "candidate_id": "candidate-1",
                "regression_kind": "task",
                "substantial": True,
            })
        self.assertEqual(SKILL_V1, (target / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual("rolled-back", self.controller.load_candidate("candidate-1")["state"])

    def test_interrupted_promotion_recovers_missing_receipt_after_restart(self):
        candidate = self.proposal()
        self.controller.evaluate("candidate-1", passing_evaluation(candidate["revision_hash"]))
        self.controller.promote("candidate-1", candidate["revision_hash"], "lost-receipt")
        self.controller.receipts_path.write_text("", encoding="utf-8")
        recovered = Controller(self.state, self.skills).promote(
            "candidate-1", candidate["revision_hash"], "recovered-receipt"
        )
        self.assertEqual("promote", recovered["action"])
        self.assertEqual("interrupted promotion receipt recovered", recovered["reason"])
        self.assertEqual(SKILL_V2, (self.skills / "helper" / "SKILL.md").read_text(encoding="utf-8"))

    def test_terminal_candidate_content_expires_but_hash_receipts_remain(self):
        candidate = self.proposal()
        self.controller.evaluate("candidate-1", passing_evaluation(candidate["revision_hash"]))
        self.controller.promote("candidate-1", candidate["revision_hash"], "promote-expiring")
        self.controller.rollback("candidate-1", "rollback-expiring")
        receipt_count = len([
            row for row in self.controller.receipts_path.read_text(encoding="utf-8").splitlines() if row
        ])
        terminal = self.controller.load_candidate("candidate-1")
        terminal["updated_at"] = (now() - timedelta(days=31)).isoformat(timespec="seconds")
        atomic_json(self.controller.candidate_path("candidate-1"), terminal)
        self.controller.prune()
        self.assertFalse(self.controller.candidate_path("candidate-1").exists())
        self.assertFalse((self.state / "snapshots" / "candidate-1").exists())
        self.assertEqual(receipt_count, len([
            row for row in self.controller.receipts_path.read_text(encoding="utf-8").splitlines() if row
        ]))

    def test_symlinked_live_skill_is_never_promoted(self):
        real = self.root / "real"
        real.mkdir()
        (real / "SKILL.md").write_text(SKILL_V1, encoding="utf-8")
        os.symlink(real, self.skills / "helper")
        candidate = self.proposal()
        self.controller.evaluate("candidate-1", passing_evaluation(candidate["revision_hash"]))
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.controller.promote("candidate-1", candidate["revision_hash"], "no-symlink")

    def test_state_and_files_are_private(self):
        candidate = self.proposal()
        self.assertEqual(0o700, self.state.stat().st_mode & 0o777)
        self.assertEqual(0o600, self.controller.candidate_path(candidate["candidate_id"]).stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
