#!/usr/bin/env python3
"""Dependency-free, host-neutral local runtime for ESRA 1.2.

The runtime stores concise structured evidence. It never starts a reasoning
cycle, edits a skill, promotes an experiment, or changes host configuration by
itself. Hosts differ only in state-directory resolution and lifecycle adapters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
OUTCOMES = {"success", "partial", "failure", "blocked", "inconclusive", "not-run"}
DECISIONS = {"adopt", "revise", "reject", "more-evidence"}
DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_id(value: str, label: str = "identifier") -> str:
    if not SAFE_ID.fullmatch(value) or value in {".", ".."}:
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def digest(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def resolve_data_dir(host: str, override: str | None = None) -> Path:
    if override:
        raw = override
    elif os.environ.get("ESRA_DATA_DIR"):
        raw = os.environ["ESRA_DATA_DIR"]
    elif host == "openai" and os.environ.get("PLUGIN_DATA"):
        raw = os.environ["PLUGIN_DATA"]
    elif host == "claude" and os.environ.get("CLAUDE_PLUGIN_DATA"):
        raw = os.environ["CLAUDE_PLUGIN_DATA"]
    elif host == "hermes":
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        raw = str(home / "esra" / "data")
    elif host == "claude":
        raw = str(Path.home() / ".claude" / "esra")
    else:
        raw = str(Path.home() / ".codex" / "esra")
    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing symlinked data directory: {path}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def _refuse_symlink(path: Path) -> None:
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing symlinked path: {path}")


def atomic_json(path: Path, payload: Any) -> None:
    _refuse_symlink(path.parent)
    _refuse_symlink(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    _refuse_symlink(path)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def append_event(base: Path, kind: str, **fields: Any) -> dict[str, Any]:
    event = {"id": uuid.uuid4().hex, "timestamp": utc_now(), "kind": kind}
    event.update({key: value for key, value in fields.items() if value not in (None, "", [])})
    encoded = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path = base / "events.jsonl"
    _refuse_symlink(path)
    max_bytes = int(os.environ.get("ESRA_MAX_LOG_BYTES", DEFAULT_MAX_LOG_BYTES))
    if path.exists() and path.stat().st_size + len(encoded) > max_bytes:
        rotated = base / "events.1.jsonl"
        _refuse_symlink(rotated)
        os.replace(path, rotated)
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, encoded)
    finally:
        os.close(descriptor)
    return event


def load_events(base: Path, limit: int | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name in ("events.1.jsonl", "events.jsonl"):
        path = base / name
        if not path.exists():
            continue
        _refuse_symlink(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records[-limit:] if limit is not None else records


def record_lifecycle(payload: dict[str, Any], host: str, base: Path) -> dict[str, Any]:
    """Store an allowlisted lifecycle counter, never content or raw identifiers."""
    return append_event(
        base,
        "lifecycle",
        host=host,
        event=str(payload.get("hook_event_name") or payload.get("event") or "Unknown"),
        session=digest(payload.get("session_id") or payload.get("sessionId")),
        turn=digest(payload.get("turn_id") or payload.get("turnId")),
        workspace=Path(str(payload.get("cwd", ""))).name or None,
    )


def trigger_score(args: argparse.Namespace) -> tuple[int, list[str]]:
    score = max(0, min(int(args.complexity), 10))
    reasons: list[str] = []
    if args.complexity >= 7:
        reasons.append("high complexity")
    if args.major_change:
        score += 3
        reasons.append("major architecture or skill change")
    if args.new_skill:
        score += 3
        reasons.append("new skill")
    if args.failures:
        score += min(args.failures * 2, 6)
        reasons.append(f"{args.failures} repeated failure(s)")
    if args.confidence < 0.5:
        score += 2
        reasons.append("low confidence")
    return min(score, 20), reasons


def command_trigger(args: argparse.Namespace, base: Path) -> int:
    score, reasons = trigger_score(args)
    history = read_json(base / "trigger-history.json", [])
    today = utc_now()[:10]
    same_session = [row for row in history if row.get("session") == digest(args.session)]
    daily = [row for row in history if str(row.get("timestamp", "")).startswith(today)]
    rate_limited = bool(same_session) or len(daily) >= 3
    recommend = score >= 10 and (args.force or not rate_limited)
    result = {
        "recommend": recommend,
        "score": score,
        "reasons": reasons,
        "rate_limited": rate_limited and not args.force,
        "note": "recommendation only; no ESRA cycle was executed",
    }
    if recommend:
        history.append({"timestamp": utc_now(), "session": digest(args.session), "score": score})
        atomic_json(base / "trigger-history.json", history[-100:])
    print(json.dumps(result, sort_keys=True))
    return 0


def command_record(args: argparse.Namespace, base: Path) -> int:
    safe_id(args.task_id, "task id")
    append_event(
        base,
        "cycle",
        task_id=args.task_id,
        outcome=args.outcome,
        evidence=args.evidence,
        change=args.change,
        verification=args.verification,
        uncertainty=args.uncertainty,
        next_review=args.next_review,
    )
    return 0


def parse_metrics(items: Iterable[str]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for item in items:
        key, separator, value = item.partition("=")
        if not separator:
            raise ValueError(f"metric must be NAME=NUMBER: {item!r}")
        safe_id(key, "metric name")
        metrics[key] = float(value)
    return metrics


def command_baseline(args: argparse.Namespace, base: Path) -> int:
    safe_id(args.name, "baseline name")
    rows = read_json(base / "baselines.json", [])
    rows.append({"name": args.name, "timestamp": utc_now(), "metrics": parse_metrics(args.metric)})
    atomic_json(base / "baselines.json", rows[-100:])
    return 0


def experiment_path(base: Path, experiment_id: str) -> Path:
    return base / "experiments" / f"{safe_id(experiment_id, 'experiment id')}.json"


def run_once(command: str, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "stdout_digest": digest(completed.stdout),
            "stderr_digest": digest(completed.stderr),
        }
    except subprocess.TimeoutExpired:
        return {"returncode": None, "duration_ms": round((time.monotonic() - started) * 1000), "timed_out": True}


def command_experiment_create(args: argparse.Namespace, base: Path) -> int:
    if args.alignment < 0.6:
        raise ValueError("alignment below 0.6; redesign the experiment before execution")
    record = {
        "id": safe_id(args.id, "experiment id"),
        "created_at": utc_now(),
        "hypothesis": args.hypothesis,
        "baseline_command": args.baseline_command,
        "candidate_command": args.candidate_command,
        "mode": args.mode,
        "timeout": args.timeout,
        "guardrail": args.guardrail,
        "rollback": args.rollback,
        "alignment": args.alignment,
        "status": "designed",
        "runs": [],
    }
    atomic_json(experiment_path(base, args.id), record)
    return 0


def command_experiment_run(args: argparse.Namespace, base: Path) -> int:
    path = experiment_path(base, args.id)
    record = read_json(path, None)
    if not isinstance(record, dict):
        raise ValueError(f"unknown experiment: {args.id}")
    order = ["baseline", "candidate"] if record["mode"] == "canary" else ["baseline", "candidate", "candidate", "baseline"]
    runs = []
    for variant in order:
        result = run_once(record[f"{variant}_command"], float(record["timeout"]))
        runs.append({"variant": variant, **result})
        if variant == "candidate" and result.get("returncode") != 0:
            break
    record["runs"] = runs
    record["status"] = "stopped" if any(row.get("returncode") != 0 for row in runs) else "completed"
    record["ran_at"] = utc_now()
    atomic_json(path, record)
    append_event(base, "experiment", experiment_id=args.id, outcome=record["status"], evidence=[path.name])
    return 0 if record["status"] == "completed" else 2


def command_experiment_decide(args: argparse.Namespace, base: Path) -> int:
    path = experiment_path(base, args.id)
    record = read_json(path, None)
    if not isinstance(record, dict):
        raise ValueError(f"unknown experiment: {args.id}")
    if not record.get("runs"):
        raise ValueError("experiment has no observed runs")
    record["decision"] = args.decision
    record["decision_evidence"] = args.evidence
    record["status"] = "reviewed"
    atomic_json(path, record)
    return 0


def command_experiment_list(_args: argparse.Namespace, base: Path) -> int:
    rows = []
    for path in sorted((base / "experiments").glob("*.json")) if (base / "experiments").exists() else []:
        value = read_json(path, {})
        rows.append({key: value.get(key) for key in ("id", "status", "decision")})
    print(json.dumps(rows, sort_keys=True))
    return 0


def command_experiment_report(args: argparse.Namespace, base: Path) -> int:
    record = read_json(experiment_path(base, args.id), None)
    if not isinstance(record, dict):
        raise ValueError(f"unknown experiment: {args.id}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    text = (
        f"# Experiment {record['id']}\n\n"
        f"- Hypothesis: {record['hypothesis']}\n"
        f"- Status: {record['status']}\n"
        f"- Decision: {record.get('decision', 'not decided')}\n"
        f"- Guardrail: {record['guardrail']}\n"
        f"- Rollback: {record['rollback']}\n"
        f"- Runs: {len(record.get('runs', []))}\n"
    )
    output.write_text(text, encoding="utf-8")
    return 0


def command_dashboard(_args: argparse.Namespace, base: Path) -> int:
    events = load_events(base)
    result = {
        "events": len(events),
        "kinds": dict(Counter(row.get("kind", "unknown") for row in events)),
        "outcomes": dict(Counter(row.get("outcome") for row in events if row.get("outcome"))),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def command_audit(args: argparse.Namespace, base: Path) -> int:
    events = [row for row in load_events(base, args.limit) if row.get("kind") == "cycle"]
    result = {
        "recorded_cycles": len(events),
        "history": "available" if events else "unknown",
        "non_success": sum(row.get("outcome") not in {"success"} for row in events),
        "missing_verification": sum(not row.get("verification") for row in events),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def command_oversight(args: argparse.Namespace, base: Path) -> int:
    proposal_id = safe_id(args.id, "proposal id")
    path = base / "oversight" / f"{proposal_id}.md"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _refuse_symlink(path)
    text = (
        f"# {args.title}\n\n"
        f"## Summary\n\n{args.summary}\n\n"
        f"## Evidence\n\n{args.evidence}\n\n"
        f"## Verification\n\n{args.verification}\n"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Host-neutral ESRA evidence and experiment runtime")
    parser.add_argument("--host", choices=("openai", "claude", "hermes"), default="openai")
    parser.add_argument("--data-dir")
    commands = parser.add_subparsers(dest="command", required=True)

    trigger = commands.add_parser("trigger", help="recommend, but never run, one bounded ESRA review")
    trigger.add_argument("--complexity", type=float, default=0)
    trigger.add_argument("--major-change", action="store_true")
    trigger.add_argument("--new-skill", action="store_true")
    trigger.add_argument("--failures", type=int, default=0)
    trigger.add_argument("--confidence", type=float, default=1.0)
    trigger.add_argument("--session", default="anonymous")
    trigger.add_argument("--force", action="store_true")
    trigger.set_defaults(function=command_trigger)

    record = commands.add_parser("record")
    record.add_argument("--task-id", required=True)
    record.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--change")
    record.add_argument("--verification")
    record.add_argument("--uncertainty")
    record.add_argument("--next-review")
    record.set_defaults(function=command_record)

    baseline = commands.add_parser("baseline")
    baseline.add_argument("--name", required=True)
    baseline.add_argument("--metric", action="append", required=True)
    baseline.set_defaults(function=command_baseline)

    experiment = commands.add_parser("experiment")
    experiment_commands = experiment.add_subparsers(dest="experiment_command", required=True)
    create = experiment_commands.add_parser("create")
    create.add_argument("--id", required=True)
    create.add_argument("--hypothesis", required=True)
    create.add_argument("--baseline-command", required=True)
    create.add_argument("--candidate-command", required=True)
    create.add_argument("--mode", choices=("canary", "ab"), default="canary")
    create.add_argument("--timeout", type=float, default=30)
    create.add_argument("--guardrail", required=True)
    create.add_argument("--rollback", required=True)
    create.add_argument("--alignment", type=float, default=1.0)
    create.set_defaults(function=command_experiment_create)
    run = experiment_commands.add_parser("run")
    run.add_argument("--id", required=True)
    run.set_defaults(function=command_experiment_run)
    decide = experiment_commands.add_parser("decide")
    decide.add_argument("--id", required=True)
    decide.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    decide.add_argument("--evidence", required=True)
    decide.set_defaults(function=command_experiment_decide)
    listing = experiment_commands.add_parser("list")
    listing.set_defaults(function=command_experiment_list)
    report = experiment_commands.add_parser("report")
    report.add_argument("--id", required=True)
    report.add_argument("--output", required=True)
    report.set_defaults(function=command_experiment_report)

    dashboard = commands.add_parser("dashboard")
    dashboard.set_defaults(function=command_dashboard)
    audit = commands.add_parser("audit")
    audit.add_argument("--limit", type=int, default=50)
    audit.set_defaults(function=command_audit)
    oversight = commands.add_parser("oversight")
    oversight.add_argument("--id", required=True)
    oversight.add_argument("--title", required=True)
    oversight.add_argument("--summary", required=True)
    oversight.add_argument("--evidence", required=True)
    oversight.add_argument("--verification", required=True)
    oversight.set_defaults(function=command_oversight)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        base = resolve_data_dir(args.host, args.data_dir)
        return int(args.function(args, base) or 0)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
