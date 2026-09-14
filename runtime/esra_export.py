#!/usr/bin/env python3
"""Export local ESRA records as deterministic, privacy-allowlisted events."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0.0"
PROTOCOL_VERSION = "1.2"
ROTATED_LOGS = ("events.1.jsonl", "events.jsonl.1", "events.jsonl")
PAYLOAD_FIELDS = {
    "task_id", "task", "change", "verification", "uncertainty",
    "next_review", "recommended", "recommend_cycle", "reason", "reasons",
    "score", "threshold", "mode", "experiment", "experiment_id", "name",
    "decision", "metrics", "host", "event", "workspace",
}


def normalize_timestamp(value: Any, fallback: float) -> str:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            pass
    return datetime.fromtimestamp(fallback, timezone.utc).isoformat(timespec="seconds")


def stable_id(record: dict[str, Any], source: str, implementation: str) -> str:
    existing = record.get("id") or record.get("run_id") or record.get("source_id")
    if existing:
        return str(existing)
    material = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{implementation}\0{source}\0{material}".encode()).hexdigest()[:32]


def event_type(kind: str) -> str:
    lowered = kind.lower()
    if "trigger" in lowered or lowered == "recommended-not-run":
        return "trigger"
    if "experiment" in lowered:
        return "experiment"
    if "audit" in lowered or "validate" in lowered:
        return "audit"
    if lowered in {"lifecycle", "baseline", "observation"}:
        return "observation"
    return "integration"


def normalized_outcome(record: dict[str, Any], kind: str) -> str | None:
    outcome = str(record.get("outcome", "")).lower()
    if outcome in {"success", "partial", "failure", "inconclusive", "not-run"}:
        return outcome
    if outcome == "blocked" or "blocked" in kind.lower():
        return "not-run"
    if outcome == "abandoned":
        return "inconclusive"
    if isinstance(record.get("success"), bool):
        return "success" if record["success"] else "failure"
    if record.get("recommended") is False or record.get("recommend_cycle") is False:
        return "not-run"
    return None


def normalize_evidence(record: dict[str, Any], source: str) -> list[str]:
    raw = record.get("evidence")
    if isinstance(raw, list):
        evidence = [str(item).strip() for item in raw if str(item).strip()]
    elif raw:
        evidence = [str(raw).strip()]
    else:
        evidence = []
    verification = str(record.get("verification", "")).strip()
    if verification and verification not in evidence:
        evidence.append(verification)
    evidence.append(f"source:{source}")
    return evidence


def load_source_records(base: Path) -> Iterable[tuple[dict[str, Any], str, float]]:
    for name in ROTATED_LOGS:
        path = base / name
        if not path.exists():
            continue
        if path.is_symlink():
            raise ValueError(f"refusing symlinked source: {path}")
        fallback = path.stat().st_mtime
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value, f"{name}:{index}", fallback


def normalize_record(record: dict[str, Any], source: str, fallback: float, implementation: str) -> dict[str, Any]:
    kind = str(record.get("kind") or record.get("record_type") or record.get("event") or "unknown")
    payload = {"source_kind": kind}
    payload.update({key: record[key] for key in sorted(PAYLOAD_FIELDS) if record.get(key) not in (None, "", [], {})})
    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "implementation": implementation,
        "id": stable_id(record, source, implementation),
        "timestamp": normalize_timestamp(record.get("timestamp") or record.get("ts"), fallback),
        "event_type": event_type(kind),
        "payload": payload,
        "evidence": normalize_evidence(record, source),
    }
    outcome = normalized_outcome(record, kind)
    if outcome:
        event["outcome"] = outcome
    return event


def export_events(base: Path, implementation: str = "esra-agents") -> list[dict[str, Any]]:
    if base.exists() and base.is_symlink():
        raise ValueError(f"refusing symlinked data directory: {base}")
    rows = [normalize_record(record, source, fallback, implementation) for record, source, fallback in load_source_records(base)]
    return rows


def write_jsonl(events: Iterable[dict[str, Any]], output: str) -> None:
    encoded = "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events)
    if output == "-":
        sys.stdout.write(encoded)
        return
    path = Path(output)
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing symlinked output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(encoded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--implementation", default="esra-agents")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        write_jsonl(export_events(Path(args.data_dir).expanduser(), args.implementation), args.output)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
