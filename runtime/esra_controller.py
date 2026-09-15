#!/usr/bin/env python3
"""Guarded autonomous ESRA controller for agent-owned skills.

Host adapters submit sanitized events and revision-bound candidates. This
module never reads host transcripts, credentials, or canonical repositories.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

SCHEMA_VERSION = "1.0.0"
PROTOCOL_VERSION = "1.2"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
HASH16 = re.compile(r"^[a-f0-9]{16}$")
HASH64 = re.compile(r"^[a-f0-9]{64}$")
URL = re.compile(r"https?://", re.IGNORECASE)
FORBIDDEN_TEXT = re.compile(
    r"(?:requires_env|api[_-]?key|credential|authorization:|install[_ -]?hook|"
    r"rm\s+-rf|mkfs\b|shutdown\b|curl\b.*\|\s*(?:sh|bash)|wget\b.*\|\s*(?:sh|bash))",
    re.IGNORECASE,
)
PROTECTED_PREFIXES = ("esra-", "controller", "evaluator", "value", "safety")
TRANSITIONS: dict[str, set[str]] = {
    "observed": {"proposed"},
    "proposed": {"aligned", "rejected"},
    "aligned": {"evaluated", "inconclusive", "rejected", "quarantined"},
    "evaluated": {"staged", "rejected", "quarantined"},
    "staged": {"active", "rolled-back", "quarantined"},
    "active": {"accepted", "rolled-back", "quarantined"},
    "accepted": {"rolled-back"},
    "inconclusive": {"aligned", "rejected"},
    "rejected": set(),
    "rolled-back": set(),
    "quarantined": set(),
}
ALLOWED_EVENT_FIELDS = {
    "host", "event_type", "outcome", "duration_ms", "error_class",
    "activated_skills", "evidence_digest", "failure_fingerprint",
    "candidate_id", "regression_kind", "substantial", "verifier_failure",
}
DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "protocol_version": PROTOCOL_VERSION,
    "mode": "guarded",
    "allowed_surfaces": ["skills", "routing"],
    "core_policy": "requires-human",
    "budgets": {
        "reviews_per_agent_day": 1,
        "experiments_per_agent_day": 1,
        "promotions_per_agent_day": 1,
    },
    "evidence": {
        "persist_raw_content": False,
        "max_ephemeral_excerpts": 4,
        "max_excerpt_bytes": 2048,
        "retention_days": 30,
    },
    "evaluation": {
        "minimum_replays": 3,
        "minimum_candidate_wins": 2,
        "blind_judge": True,
        "critical_regressions_allowed": 0,
    },
    "canary": {
        "eligible_tasks": 5,
        "maximum_days": 7,
        "task_regressions_before_rollback": 2,
    },
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return now().isoformat(timespec="seconds")


def digest(value: Any, length: int = 64) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()[:length]


def safe_id(value: str, label: str = "identifier") -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    return path.as_posix()


def refuse_symlink(path: Path) -> None:
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing symlinked path: {path}")


def secure_dir(path: Path) -> Path:
    refuse_symlink(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def atomic_json(path: Path, value: Any) -> None:
    secure_dir(path.parent)
    refuse_symlink(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    refuse_symlink(path)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    secure_dir(path.parent)
    refuse_symlink(path)
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    refuse_symlink(path)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def redact_excerpts(excerpts: list[str], secret_values: list[str] | None = None) -> list[str]:
    """Return bounded reviewer-only excerpts; callers must never persist them."""
    secrets = [value for value in (secret_values or []) if value]
    redacted: list[str] = []
    for excerpt in excerpts[: DEFAULT_POLICY["evidence"]["max_ephemeral_excerpts"]]:
        value = str(excerpt)
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)(?:api[_-]?key|token|password)\s*[:=]\s*\S+", "secret=[REDACTED]", value)
        encoded = value.encode("utf-8")[: DEFAULT_POLICY["evidence"]["max_excerpt_bytes"]]
        redacted.append(encoded.decode("utf-8", errors="ignore"))
    return redacted


class Controller:
    def __init__(self, state_dir: Path | str, skills_root: Path | str | None = None):
        self.state = secure_dir(Path(state_dir).expanduser())
        self.skills_root = Path(skills_root).expanduser() if skills_root else None
        if self.skills_root:
            secure_dir(self.skills_root)
        self.policy_path = self.state / "policy.json"
        if not self.policy_path.exists():
            atomic_json(self.policy_path, DEFAULT_POLICY)
        self.policy = read_json(self.policy_path)
        self.events_path = self.state / "events.jsonl"
        self.receipts_path = self.state / "receipts.jsonl"
        self.budget_events_path = self.state / "budget-events.jsonl"
        self.tokens_path = self.state / "apply-tokens.json"
        self.reviews_path = self.state / "review-queue.jsonl"
        secure_dir(self.state / "candidates")
        secure_dir(self.state / "snapshots")
        secure_dir(self.state / "locks")

    def agent_hash(self, agent_id: str) -> str:
        return digest(agent_id, 16)

    @contextlib.contextmanager
    def lock(self, agent_hash: str) -> Iterator[None]:
        if not HASH16.fullmatch(agent_hash):
            raise ValueError("invalid agent hash")
        path = self.state / "locks" / f"{agent_hash}.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError(f"agent is already locked: {agent_hash}") from exc
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def candidate_path(self, candidate_id: str) -> Path:
        return self.state / "candidates" / f"{safe_id(candidate_id, 'candidate id')}.json"

    def load_candidate(self, candidate_id: str) -> dict[str, Any]:
        value = read_json(self.candidate_path(candidate_id))
        if not isinstance(value, dict):
            raise ValueError(f"unknown candidate: {candidate_id}")
        return value

    def save_candidate(self, candidate: dict[str, Any]) -> None:
        candidate["updated_at"] = timestamp()
        atomic_json(self.candidate_path(candidate["candidate_id"]), candidate)

    def transition(self, candidate: dict[str, Any], destination: str, reason: str) -> None:
        source = candidate["state"]
        if destination not in TRANSITIONS.get(source, set()):
            raise ValueError(f"invalid state transition: {source} -> {destination}")
        candidate["state"] = destination
        candidate.setdefault("transitions", []).append({
            "from": source,
            "to": destination,
            "timestamp": timestamp(),
            "reason": reason,
            "candidate_id": candidate["candidate_id"],
            "revision_hash": candidate["revision_hash"],
            "correlation_id": candidate["correlation_id"],
            "idempotency_key": f"transition:{candidate['candidate_id']}:{destination}:{candidate['revision_hash']}",
            "evidence_hashes": list(candidate.get("evidence_hashes", [])),
        })

    def _receipt_by_key(self, key: str) -> dict[str, Any] | None:
        return next((row for row in load_jsonl(self.receipts_path) if row.get("idempotency_key") == key), None)

    def _receipt(self, candidate: dict[str, Any], action: str, key: str, **extra: Any) -> dict[str, Any]:
        existing = self._receipt_by_key(key)
        if existing:
            return existing
        receipt = {
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "receipt_id": uuid.uuid4().hex,
            "candidate_id": candidate["candidate_id"],
            "revision_hash": candidate["revision_hash"],
            "correlation_id": candidate["correlation_id"],
            "idempotency_key": key,
            "agent_hash": candidate["agent_hash"],
            "action": action,
            "timestamp": timestamp(),
            "evidence_hashes": list(candidate.get("evidence_hashes", [])),
            **extra,
        }
        append_jsonl(self.receipts_path, receipt)
        return receipt

    def _today_count(self, agent_hash: str, action: str) -> int:
        today = now().date()
        return sum(
            row.get("agent_hash") == agent_hash
            and row.get("action") == action
            and parse_time(row["timestamp"]).date() == today
            for row in load_jsonl(self.receipts_path) + load_jsonl(self.budget_events_path)
        )

    def _record_budget(self, agent_hash: str, action: str, correlation_id: str, key: str) -> dict[str, Any]:
        existing = next(
            (row for row in load_jsonl(self.budget_events_path) if row.get("idempotency_key") == key),
            None,
        )
        if existing:
            return existing
        event = {
            "agent_hash": agent_hash,
            "action": action,
            "correlation_id": correlation_id,
            "idempotency_key": key,
            "timestamp": timestamp(),
        }
        append_jsonl(self.budget_events_path, event)
        return event

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in {"paused", "proposal-only", "guarded"}:
            raise ValueError(f"invalid mode: {mode}")
        self.policy["mode"] = mode
        atomic_json(self.policy_path, self.policy)
        return self.policy

    def issue_apply_token(
        self,
        candidate_id: str,
        revision_hash: str,
        host_revision_hash: str,
        ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        if candidate.get("state") != "evaluated" or candidate.get("evaluation", {}).get("decision") != "pass":
            raise ValueError("candidate has not passed evaluation")
        if candidate.get("requires_human"):
            raise ValueError("candidate requires human approval")
        if revision_hash != candidate["revision_hash"] or not HASH64.fullmatch(revision_hash):
            raise ValueError("stale candidate revision")
        if not HASH64.fullmatch(host_revision_hash):
            raise ValueError("invalid host revision hash")
        token = f"esra:{candidate_id}:{uuid.uuid4().hex}"
        record = {
            "candidate_id": candidate_id,
            "revision_hash": revision_hash,
            "host_revision_hash": host_revision_hash,
            "token_hash": digest(token),
            "expires_at": (now() + timedelta(seconds=max(1, min(ttl_seconds, 3600)))).isoformat(timespec="seconds"),
            "consumed": False,
        }
        tokens = read_json(self.tokens_path, {})
        tokens[record["token_hash"]] = record
        atomic_json(self.tokens_path, tokens)
        return {"apply_token": token, "expires_at": record["expires_at"]}

    def consume_apply_token(self, token: str, candidate_id: str, host_revision_hash: str) -> dict[str, Any]:
        token_hash = digest(token)
        tokens = read_json(self.tokens_path, {})
        record = tokens.get(token_hash)
        if not isinstance(record, dict):
            raise ValueError("unknown apply token")
        candidate = self.load_candidate(candidate_id)
        with self.lock(candidate["agent_hash"]):
            tokens = read_json(self.tokens_path, {})
            record = tokens.get(token_hash)
            if not isinstance(record, dict) or record.get("consumed") is True:
                raise ValueError("apply token already consumed")
            if parse_time(record["expires_at"]) < now():
                raise ValueError("apply token expired")
            if record.get("candidate_id") != candidate_id:
                raise ValueError("apply token candidate mismatch")
            if record.get("revision_hash") != candidate.get("revision_hash"):
                raise ValueError("stale candidate revision")
            if record.get("host_revision_hash") != host_revision_hash:
                raise ValueError("apply token host revision mismatch")
            if candidate.get("state") not in {"evaluated", "staged"} or candidate.get("evaluation", {}).get("decision") != "pass":
                raise ValueError("candidate is not eligible for apply")
            record["consumed"] = True
            record["consumed_at"] = timestamp()
            tokens[token_hash] = record
            atomic_json(self.tokens_path, tokens)
        return {"authorized": True, "candidate_id": candidate_id, "revision_hash": candidate["revision_hash"]}

    def ingest(self, event: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(event.get("agent_id", ""))
        if not agent_id:
            raise ValueError("agent_id is required")
        correlation = str(event.get("correlation_id", ""))
        if correlation.startswith("esra:") or event.get("esra_generated") is True:
            return {"ignored": True, "reason": "recursion-suppressed"}
        persisted = {key: event[key] for key in ALLOWED_EVENT_FIELDS if key in event}
        persisted.update({
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "event_id": uuid.uuid4().hex,
            "timestamp": timestamp(),
            "agent_hash": self.agent_hash(agent_id),
        })
        for forbidden in ("prompt", "transcript", "messages", "tool_input", "tool_output", "session_id", "run_id"):
            if forbidden in persisted:
                raise ValueError(f"forbidden persisted field: {forbidden}")
        append_jsonl(self.events_path, persisted)
        candidate_id = persisted.get("candidate_id")
        if candidate_id:
            try:
                candidate_path = self.candidate_path(str(candidate_id))
            except ValueError:
                candidate_path = None
            if candidate_path and candidate_path.exists():
                self._observe_canary(str(candidate_id), persisted)
        self.prune()
        return persisted

    def prune(self) -> None:
        cutoff = now() - timedelta(days=int(self.policy["evidence"]["retention_days"]))
        for path in (self.events_path, self.budget_events_path, self.reviews_path):
            if not path.exists():
                continue
            rows = [row for row in load_jsonl(path) if parse_time(row["timestamp"]) >= cutoff]
            fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=self.state)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    for row in rows:
                        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                os.chmod(temporary, 0o600)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        tokens = {
            key: value for key, value in read_json(self.tokens_path, {}).items()
            if isinstance(value, dict) and parse_time(value["expires_at"]) >= now()
        }
        atomic_json(self.tokens_path, tokens)
        terminal = {"accepted", "rolled-back", "rejected", "quarantined"}
        for candidate_path in sorted((self.state / "candidates").glob("*.json")):
            candidate = read_json(candidate_path)
            if candidate.get("state") not in terminal or parse_time(candidate["updated_at"]) >= cutoff:
                continue
            snapshot_root = self.state / "snapshots" / candidate_path.stem
            if snapshot_root.exists():
                for path in sorted(snapshot_root.rglob("*"), reverse=True):
                    path.chmod(0o700 if path.is_dir() else 0o600)
                snapshot_root.chmod(0o700)
                shutil.rmtree(snapshot_root)
            candidate_path.unlink()

    def tick(self, agent_id: str, nightly: bool = False) -> dict[str, Any]:
        agent_hash = self.agent_hash(agent_id)
        self._complete_expired_canaries(agent_hash)
        if self.policy["mode"] == "paused":
            return {"review": False, "reason": "paused"}
        if self._today_count(agent_hash, "review") >= self.policy["budgets"]["reviews_per_agent_day"]:
            return {"review": False, "reason": "daily-budget"}
        cutoff = now() - timedelta(days=7)
        rows = [row for row in load_jsonl(self.events_path) if row.get("agent_hash") == agent_hash and parse_time(row["timestamp"]) >= cutoff]
        verifier = any(row.get("verifier_failure") is True for row in rows)
        fingerprints: dict[str, int] = {}
        for row in rows:
            if row.get("outcome") == "failure" or row.get("event_type") == "user_correction":
                value = str(row.get("failure_fingerprint") or row.get("error_class") or "")
                if value:
                    fingerprints[value] = fingerprints.get(value, 0) + 1
        repeated = next((key for key, count in fingerprints.items() if count >= 2), None)
        substantial = sum(row.get("substantial") is True for row in rows)
        eligible = verifier or repeated is not None or (nightly and substantial >= 3)
        if not eligible:
            return {"review": False, "reason": "insufficient-evidence"}
        correlation = f"esra:{uuid.uuid4().hex}"
        self._record_budget(agent_hash, "review", correlation, f"review:{agent_hash}:{now().date()}")
        reason = "verifier" if verifier else "repeated-failure" if repeated else "nightly"
        append_jsonl(self.reviews_path, {
            "agent_hash": agent_hash,
            "correlation_id": correlation,
            "idempotency_key": f"review:{agent_hash}:{now().date()}",
            "reason": reason,
            "status": "pending",
            "timestamp": timestamp(),
            "evidence_hash": digest([verifier, repeated, substantial], 16),
        })
        return {"review": True, "correlation_id": correlation, "reason": reason}

    def next_review(self, agent_id: str) -> dict[str, Any]:
        agent_hash = self.agent_hash(agent_id)
        latest: dict[str, dict[str, Any]] = {}
        for row in load_jsonl(self.reviews_path):
            if row.get("agent_hash") == agent_hash:
                latest[str(row.get("correlation_id"))] = row
        pending = next((row for row in latest.values() if row.get("status") == "pending"), None)
        if not pending:
            return {"review": None}
        claimed = {**pending, "status": "claimed", "claimed_at": timestamp(), "timestamp": timestamp()}
        append_jsonl(self.reviews_path, claimed)
        return {"review": claimed}

    def complete_review(self, agent_id: str, correlation_id: str, outcome: str, evidence_hash: str) -> dict[str, Any]:
        if outcome not in {"proposed", "no-change", "inconclusive", "requires-human"}:
            raise ValueError("invalid review outcome")
        if not HASH16.fullmatch(evidence_hash) and not HASH64.fullmatch(evidence_hash):
            raise ValueError("review evidence must be a hash")
        agent_hash = self.agent_hash(agent_id)
        latest = next(
            (row for row in reversed(load_jsonl(self.reviews_path))
             if row.get("agent_hash") == agent_hash and row.get("correlation_id") == correlation_id),
            None,
        )
        if not latest or latest.get("status") != "claimed":
            raise ValueError("review is not claimed")
        completed = {
            **latest,
            "status": "completed",
            "outcome": outcome,
            "result_evidence_hash": evidence_hash,
            "completed_at": timestamp(),
            "timestamp": timestamp(),
        }
        append_jsonl(self.reviews_path, completed)
        return completed

    def classify(self, target: str, surface: str, files: dict[str, str]) -> list[str]:
        reasons: list[str] = []
        lowered = target.lower()
        if lowered.startswith(PROTECTED_PREFIXES):
            reasons.append("protected-core-target")
        if surface not in self.policy["allowed_surfaces"]:
            reasons.append("surface-not-allowed")
        if not files or "SKILL.md" not in files:
            reasons.append("missing-skill-md")
        total = 0
        for name, content in files.items():
            safe_relative(name)
            if not isinstance(content, str):
                reasons.append("non-text-file")
                continue
            total += len(content.encode("utf-8"))
            if URL.search(content):
                reasons.append("network-endpoint")
            if FORBIDDEN_TEXT.search(content):
                reasons.append("privileged-or-dangerous-content")
        if total > 40_000:
            reasons.append("candidate-too-large")
        return sorted(set(reasons))

    def propose(self, proposal: dict[str, Any]) -> dict[str, Any]:
        candidate_id = safe_id(str(proposal.get("candidate_id", "")), "candidate id")
        target = safe_id(str(proposal.get("target", "")), "target")
        surface = str(proposal.get("surface", "skills"))
        agent_id = str(proposal.get("agent_id", ""))
        if not agent_id:
            raise ValueError("agent_id is required")
        agent_hash = self.agent_hash(agent_id)
        files = proposal.get("files")
        if not isinstance(files, dict):
            raise ValueError("files must be an object of relative path to text")
        normalized = {safe_relative(str(key)): value for key, value in files.items()}
        revision = digest(normalized)
        supplied = proposal.get("revision_hash")
        if supplied and supplied != revision:
            raise ValueError("supplied revision hash does not match candidate files")
        idempotency_key = str(proposal.get("idempotency_key") or f"proposal:{candidate_id}:{revision}")
        existing = read_json(self.candidate_path(candidate_id))
        if existing:
            if existing.get("idempotency_key") == idempotency_key and existing.get("revision_hash") == revision:
                return existing
            raise ValueError(f"candidate already exists: {candidate_id}")
        reasons = self.classify(target, surface, normalized)
        candidate = {
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "candidate_id": candidate_id,
            "revision_hash": revision,
            "correlation_id": str(proposal.get("correlation_id") or f"esra:{uuid.uuid4().hex}"),
            "idempotency_key": idempotency_key,
            "agent_hash": agent_hash,
            "surface": surface,
            "target": target,
            "state": "observed",
            "evidence_hashes": list(proposal.get("evidence_hashes", [])),
            "requires_human": bool(reasons),
            "risk_reasons": reasons,
            "files": normalized,
            "created_at": timestamp(),
            "updated_at": timestamp(),
            "transitions": [],
        }
        self.transition(candidate, "proposed", "candidate registered")
        self.save_candidate(candidate)
        return candidate

    def evaluate(self, candidate_id: str, evaluation: dict[str, Any]) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        if evaluation.get("revision_hash") != candidate["revision_hash"]:
            raise ValueError("stale candidate revision")
        if candidate["state"] not in {"proposed", "aligned", "inconclusive"}:
            raise ValueError(f"candidate cannot be evaluated from {candidate['state']}")
        budget_key = str(evaluation.get("idempotency_key") or f"evaluation:{candidate_id}:{candidate['revision_hash']}")
        previous_budget = next(
            (row for row in load_jsonl(self.budget_events_path) if row.get("idempotency_key") == budget_key),
            None,
        )
        if not previous_budget and self._today_count(candidate["agent_hash"], "experiment") >= self.policy["budgets"]["experiments_per_agent_day"]:
            raise ValueError("daily experiment budget exhausted")
        if candidate["state"] in {"proposed", "inconclusive"}:
            self.transition(candidate, "aligned", "alignment evaluation started")
        replays = evaluation.get("replays", [])
        minimum = self.policy["evaluation"]["minimum_replays"]
        wins = sum(row.get("judge") == "candidate" for row in replays if isinstance(row, dict))
        critical = any(row.get("critical_regression") is True for row in replays if isinstance(row, dict))
        valid = (
            evaluation.get("deterministic_pass") is True
            and evaluation.get("alignment_decision") == "allow"
            and evaluation.get("blind") is True
            and evaluation.get("proposal_context_visible") is False
            and len(replays) >= minimum
            and wins >= self.policy["evaluation"]["minimum_candidate_wins"]
            and not critical
        )
        hard_block = critical or evaluation.get("alignment_decision") == "block" or evaluation.get("deterministic_pass") is False
        decision = "pass" if valid else "block" if hard_block else "inconclusive"
        self.transition(
            candidate,
            "evaluated" if valid else "quarantined" if hard_block else "inconclusive",
            f"evaluation {decision}",
        )
        candidate["evaluation"] = {
            "schema_version": SCHEMA_VERSION,
            "protocol_version": PROTOCOL_VERSION,
            "candidate_id": candidate_id,
            "revision_hash": candidate["revision_hash"],
            "correlation_id": candidate["correlation_id"],
            "idempotency_key": budget_key,
            "deterministic_pass": evaluation.get("deterministic_pass") is True,
            "alignment_decision": evaluation.get("alignment_decision", "revise"),
            "blind": evaluation.get("blind") is True,
            "proposal_context_visible": evaluation.get("proposal_context_visible") is True,
            "replays": replays,
            "decision": decision,
            "candidate_wins": wins,
            "evidence_hashes": list(evaluation.get("evidence_hashes", [])),
        }
        self._record_budget(candidate["agent_hash"], "experiment", candidate["correlation_id"], budget_key)
        self.save_candidate(candidate)
        return candidate

    def _target(self, candidate: dict[str, Any]) -> Path:
        if not self.skills_root:
            raise ValueError("skills root is required for promotion")
        root = secure_dir(self.skills_root.resolve())
        target = root / safe_id(candidate["target"], "target")
        refuse_symlink(target)
        if target.exists() and any(path.is_symlink() for path in target.rglob("*")):
            raise ValueError(f"refusing skill tree containing symlink: {target}")
        return target

    @staticmethod
    def _live_revision(target: Path) -> str:
        live: dict[str, str] = {}
        if not target.exists():
            return digest(live)
        for path in sorted(target.rglob("*")):
            if path.is_symlink():
                raise ValueError("live skill contains a symlink")
            if path.is_file():
                live[path.relative_to(target).as_posix()] = path.read_text(encoding="utf-8")
        return digest(live)

    def stage_external(self, candidate_id: str, revision_hash: str | None = None) -> dict[str, Any]:
        """Snapshot without mutation for a host-native skill workflow."""
        candidate = self.load_candidate(candidate_id)
        revision_hash = revision_hash or candidate["revision_hash"]
        if revision_hash != candidate["revision_hash"]:
            raise ValueError("stale candidate revision")
        if candidate.get("requires_human"):
            raise ValueError("candidate requires human approval")
        if candidate.get("evaluation", {}).get("decision") != "pass":
            raise ValueError("candidate has not passed evaluation")
        target = self._target(candidate)
        with self.lock(candidate["agent_hash"]):
            if candidate["state"] == "evaluated":
                self.transition(candidate, "staged", "host-native mutation staged")
            elif candidate["state"] != "staged":
                raise ValueError(f"candidate cannot stage from {candidate['state']}")
            snapshot = secure_dir(self.state / "snapshots" / candidate_id / revision_hash)
            if not any(snapshot.iterdir()):
                if target.exists():
                    shutil.copytree(target, snapshot / "skill", symlinks=False)
                else:
                    absent = snapshot / ".absent"
                    absent.write_text("new skill\n", encoding="utf-8")
                    absent.chmod(0o400)
                for path in sorted(snapshot.rglob("*"), reverse=True):
                    path.chmod(0o500 if path.is_dir() else 0o400)
                snapshot.chmod(0o500)
            candidate["snapshot_hash"] = digest(sorted(str(path.relative_to(snapshot)) for path in snapshot.rglob("*")))
            self.save_candidate(candidate)
        return candidate

    def complete_external(self, candidate_id: str, revision_hash: str | None, idempotency_key: str) -> dict[str, Any]:
        """Record a host-native mutation only when the exact evaluated tree is live."""
        existing = self._receipt_by_key(idempotency_key)
        if existing:
            return existing
        candidate = self.load_candidate(candidate_id)
        revision_hash = revision_hash or candidate["revision_hash"]
        if revision_hash != candidate["revision_hash"] or candidate.get("state") != "staged":
            raise ValueError("candidate is not staged at this revision")
        target = self._target(candidate)
        if self._live_revision(target) != revision_hash:
            raise ValueError("host applied content does not match evaluated revision")
        self.transition(candidate, "active", "host-native workflow activated exact revision")
        candidate["activated_at"] = timestamp()
        candidate["canary"] = {"eligible_tasks": 0, "task_regressions": 0, "critical_regressions": 0}
        self.save_candidate(candidate)
        return self._receipt(candidate, "promote", idempotency_key, snapshot_hash=candidate.get("snapshot_hash"), reason="host-native workflow completed")

    def promote(self, candidate_id: str, revision_hash: str, idempotency_key: str) -> dict[str, Any]:
        existing = self._receipt_by_key(idempotency_key)
        if existing:
            return existing
        candidate = self.load_candidate(candidate_id)
        if revision_hash != candidate["revision_hash"] or not HASH64.fullmatch(revision_hash):
            raise ValueError("stale candidate revision")
        if self.policy["mode"] != "guarded":
            raise ValueError(f"promotion disabled in mode {self.policy['mode']}")
        if candidate["requires_human"]:
            raise ValueError("candidate requires human approval")
        if candidate.get("state") == "active" and self._live_revision(self._target(candidate)) == revision_hash:
            return self._receipt(candidate, "promote", idempotency_key, snapshot_hash=candidate.get("snapshot_hash"), reason="interrupted promotion receipt recovered")
        if candidate["state"] not in {"evaluated", "staged"} or candidate.get("evaluation", {}).get("decision") != "pass":
            raise ValueError("candidate has not passed evaluation")
        if self._today_count(candidate["agent_hash"], "promote") >= self.policy["budgets"]["promotions_per_agent_day"]:
            raise ValueError("daily promotion budget exhausted")
        target = self._target(candidate)
        with self.lock(candidate["agent_hash"]):
            if candidate["state"] == "evaluated":
                self.transition(candidate, "staged", "immutable snapshot creation started")
                self.save_candidate(candidate)
            snapshot = secure_dir(self.state / "snapshots" / candidate_id / revision_hash)
            absent = snapshot / ".absent"
            if target.exists() and not any(snapshot.iterdir()):
                shutil.copytree(target, snapshot / "skill", symlinks=False)
            elif not target.exists() and not any(snapshot.iterdir()):
                absent.write_text("new skill\n", encoding="utf-8")
                absent.chmod(0o400)
            stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.esra-stage-", dir=target.parent))
            try:
                for relative, content in candidate["files"].items():
                    output = stage / safe_relative(relative)
                    secure_dir(output.parent)
                    output.write_text(content, encoding="utf-8")
                    output.chmod(0o600)
                old = target.parent / f".{target.name}.esra-old-{uuid.uuid4().hex}"
                if target.exists():
                    os.replace(target, old)
                try:
                    os.replace(stage, target)
                except Exception:
                    if old.exists():
                        os.replace(old, target)
                    raise
                if old.exists():
                    shutil.rmtree(old)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
            for path in sorted(snapshot.rglob("*"), reverse=True):
                path.chmod(0o500 if path.is_dir() else 0o400)
            snapshot.chmod(0o500)
            self.transition(candidate, "active", "exact evaluated revision activated")
            candidate["activated_at"] = timestamp()
            candidate["canary"] = {"eligible_tasks": 0, "task_regressions": 0, "critical_regressions": 0}
            candidate["snapshot_hash"] = digest(sorted(str(path.relative_to(snapshot)) for path in snapshot.rglob("*")))
            self.save_candidate(candidate)
        return self._receipt(candidate, "promote", idempotency_key, snapshot_hash=candidate["snapshot_hash"], reason="guarded evaluation passed")

    def rollback(self, candidate_id: str, idempotency_key: str, reason: str = "operator-requested") -> dict[str, Any]:
        existing = self._receipt_by_key(idempotency_key)
        if existing:
            return existing
        candidate = self.load_candidate(candidate_id)
        if candidate["state"] not in {"active", "accepted"}:
            raise ValueError(f"candidate cannot roll back from {candidate['state']}")
        target = self._target(candidate)
        snapshot = self.state / "snapshots" / candidate_id / candidate["revision_hash"]
        refuse_symlink(snapshot)
        with self.lock(candidate["agent_hash"]):
            replacement = Path(tempfile.mkdtemp(prefix=f".{target.name}.esra-rollback-", dir=target.parent))
            shutil.rmtree(replacement)
            if (snapshot / "skill").exists():
                shutil.copytree(snapshot / "skill", replacement)
                for path in sorted(replacement.rglob("*"), reverse=True):
                    path.chmod(0o700 if path.is_dir() else 0o600)
                replacement.chmod(0o700)
            old = target.parent / f".{target.name}.esra-quarantine-{uuid.uuid4().hex}"
            if target.exists():
                os.replace(target, old)
            if replacement.exists():
                os.replace(replacement, target)
            if old.exists():
                shutil.rmtree(old)
            self.transition(candidate, "rolled-back", reason)
            candidate["rollback_reason"] = reason
            self.save_candidate(candidate)
        receipt = self._receipt(candidate, "rollback", idempotency_key, snapshot_hash=candidate.get("snapshot_hash"), reason=reason)
        self._receipt(candidate, "quarantine", f"quarantine:{candidate_id}:{candidate['revision_hash']}", snapshot_hash=candidate.get("snapshot_hash"), reason=reason)
        return receipt

    def _observe_canary(self, candidate_id: str, event: dict[str, Any]) -> None:
        candidate = self.load_candidate(candidate_id)
        if candidate.get("state") != "active":
            return
        canary = candidate["canary"]
        if event.get("substantial") is True:
            canary["eligible_tasks"] += 1
        regression = event.get("regression_kind")
        if regression in {"safety", "privacy"}:
            canary["critical_regressions"] += 1
        elif regression == "task":
            canary["task_regressions"] += 1
        self.save_candidate(candidate)
        if canary["critical_regressions"] >= 1 or canary["task_regressions"] >= self.policy["canary"]["task_regressions_before_rollback"]:
            self.rollback(candidate_id, f"auto-rollback:{candidate_id}:{candidate['revision_hash']}", reason=f"canary-{regression}-regression")
        elif canary["eligible_tasks"] >= self.policy["canary"]["eligible_tasks"]:
            self.transition(candidate, "accepted", "canary completed")
            self.save_candidate(candidate)
            self._receipt(candidate, "accept", f"accept:{candidate_id}:{candidate['revision_hash']}", snapshot_hash=candidate.get("snapshot_hash"), reason="canary completed")

    def _complete_expired_canaries(self, agent_hash: str) -> None:
        maximum = timedelta(days=int(self.policy["canary"]["maximum_days"]))
        for path in sorted((self.state / "candidates").glob("*.json")):
            candidate = read_json(path)
            if candidate.get("agent_hash") != agent_hash or candidate.get("state") != "active":
                continue
            canary = candidate.get("canary", {})
            if (
                now() - parse_time(candidate["activated_at"]) >= maximum
                and not canary.get("critical_regressions")
                and not canary.get("task_regressions")
            ):
                self.transition(candidate, "accepted", "seven-day canary completed")
                self.save_candidate(candidate)
                self._receipt(
                    candidate,
                    "accept",
                    f"accept:{candidate['candidate_id']}:{candidate['revision_hash']}",
                    snapshot_hash=candidate.get("snapshot_hash"),
                    reason="seven-day canary completed",
                )

    def status(self) -> dict[str, Any]:
        candidates = [read_json(path) for path in sorted((self.state / "candidates").glob("*.json"))]
        return {"mode": self.policy["mode"], "candidates": candidates, "events": len(load_jsonl(self.events_path)), "receipts": len(load_jsonl(self.receipts_path))}

    def audit(self) -> dict[str, Any]:
        candidates = self.status()["candidates"]
        return {
            "states": {state: sum(row.get("state") == state for row in candidates) for state in sorted({row.get("state") for row in candidates})},
            "protected_pending": sum(row.get("requires_human") is True and row.get("state") in {"proposed", "evaluated", "inconclusive"} for row in candidates),
            "raw_content_persisted": False,
        }


def load_input(path: str | None) -> dict[str, Any]:
    text = sys.stdin.read() if not path or path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Guarded autonomous ESRA controller")
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--skills-root")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("ingest", "propose", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--input")
        if name == "evaluate":
            command.add_argument("--candidate", required=True)
    tick = commands.add_parser("tick")
    tick.add_argument("--agent", required=True)
    tick.add_argument("--nightly", action="store_true")
    next_review = commands.add_parser("next-review")
    next_review.add_argument("--agent", required=True)
    complete_review = commands.add_parser("complete-review")
    complete_review.add_argument("--agent", required=True)
    complete_review.add_argument("--correlation", required=True)
    complete_review.add_argument("--outcome", required=True)
    complete_review.add_argument("--evidence-hash", required=True)
    promote = commands.add_parser("promote")
    promote.add_argument("--candidate", required=True)
    promote.add_argument("--revision", required=True)
    promote.add_argument("--idempotency-key", required=True)
    stage_external = commands.add_parser("stage-external")
    stage_external.add_argument("--candidate", required=True)
    stage_external.add_argument("--revision")
    complete_external = commands.add_parser("complete-external")
    complete_external.add_argument("--candidate", required=True)
    complete_external.add_argument("--revision")
    complete_external.add_argument("--idempotency-key", required=True)
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--candidate", required=True)
    rollback.add_argument("--idempotency-key", required=True)
    rollback.add_argument("--reason", default="operator-requested")
    issue = commands.add_parser("issue-token")
    issue.add_argument("--candidate", required=True)
    issue.add_argument("--revision", required=True)
    issue.add_argument("--host-revision", required=True)
    issue.add_argument("--ttl-seconds", type=int, default=900)
    consume = commands.add_parser("consume-token")
    consume.add_argument("--candidate", required=True)
    consume.add_argument("--host-revision", required=True)
    consume.add_argument("--token", required=True)
    commands.add_parser("status")
    commands.add_parser("audit")
    commands.add_parser("pause")
    commands.add_parser("resume")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        controller = Controller(args.state_dir, args.skills_root)
        if args.command == "ingest":
            result = controller.ingest(load_input(args.input))
        elif args.command == "tick":
            result = controller.tick(args.agent, args.nightly)
        elif args.command == "next-review":
            result = controller.next_review(args.agent)
        elif args.command == "complete-review":
            result = controller.complete_review(args.agent, args.correlation, args.outcome, args.evidence_hash)
        elif args.command == "propose":
            result = controller.propose(load_input(args.input))
        elif args.command == "evaluate":
            result = controller.evaluate(args.candidate, load_input(args.input))
        elif args.command == "promote":
            result = controller.promote(args.candidate, args.revision, args.idempotency_key)
        elif args.command == "stage-external":
            result = controller.stage_external(args.candidate, args.revision)
        elif args.command == "complete-external":
            result = controller.complete_external(args.candidate, args.revision, args.idempotency_key)
        elif args.command == "rollback":
            result = controller.rollback(args.candidate, args.idempotency_key, args.reason)
        elif args.command == "issue-token":
            result = controller.issue_apply_token(args.candidate, args.revision, args.host_revision, args.ttl_seconds)
        elif args.command == "consume-token":
            result = controller.consume_apply_token(args.token, args.candidate, args.host_revision)
        elif args.command == "status":
            result = controller.status()
        elif args.command == "audit":
            result = controller.audit()
        elif args.command == "pause":
            result = controller.set_mode("paused")
        else:
            result = controller.set_mode("guarded")
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
