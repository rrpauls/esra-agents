#!/usr/bin/env python3
"""Normalize privacy-bounded MCP evidence receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
PROVIDERS = {"github", "codex-security", "browser-host-pilot", "sofa"}
STATUSES = {"success", "partial", "failure", "inconclusive", "not-run"}
OPTIONAL_FIELDS = ("revision", "workflow", "operation")
FORBIDDEN_PARTS = {
    "prompt", "transcript", "secret", "token", "password", "credential",
    "session", "cookie", "authorization", "tool_input", "tool_output",
    "email", "api_key", "access_key", "private_key", "raw_run",
}


def _key_is_forbidden(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in FORBIDDEN_PARTS)


def _reject_sensitive(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _key_is_forbidden(str(key)):
                raise ValueError(f"sensitive field is not allowed: {path}.{key}")
            _reject_sensitive(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive(item, f"{path}[{index}]")


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be an ISO-8601 string") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _metrics(value: Any) -> dict[str, str | int | float | bool]:
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise ValueError("metrics must be an object")
    projected: dict[str, str | int | float | bool] = {}
    for key in sorted(value):
        item = value[key]
        if _key_is_forbidden(str(key)):
            raise ValueError(f"sensitive metric is not allowed: {key}")
        if not isinstance(item, (str, int, float, bool)) or len(str(item)) > 256:
            raise ValueError(f"metric must be a short scalar: {key}")
        projected[str(key)] = item
    return projected


def normalize_receipt(source: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("receipt must be an object")
    _reject_sensitive(source)
    provider = str(source.get("provider", ""))
    status = str(source.get("status", ""))
    subject = str(source.get("subject", "")).strip()
    kind = str(source.get("kind", "")).strip()
    if provider not in PROVIDERS:
        raise ValueError(f"unsupported provider: {provider or '<missing>'}")
    if status not in STATUSES:
        raise ValueError(f"unsupported status: {status or '<missing>'}")
    if not subject or len(subject) > 256 or not kind or len(kind) > 128:
        raise ValueError("subject and kind must be non-empty bounded strings")
    evidence = source.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(item, str) and item.strip() for item in evidence):
        raise ValueError("evidence must be a list of non-empty strings")
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "kind": kind,
        "observed_at": _timestamp(source.get("observed_at")),
        "subject": subject,
        "status": status,
        "evidence_hashes": sorted({hashlib.sha256(item.strip().encode()).hexdigest() for item in evidence}),
        "metrics": _metrics(source.get("metrics")),
    }
    for field in OPTIONAL_FIELDS:
        value = source.get(field)
        if value not in (None, ""):
            text = str(value).strip()
            if len(text) > 256:
                raise ValueError(f"{field} exceeds 256 characters")
            receipt[field] = text
    material = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    receipt["receipt_id"] = hashlib.sha256(material.encode()).hexdigest()[:32]
    return receipt


def write_receipt(receipt: dict[str, Any], output: str) -> None:
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    if output == "-":
        sys.stdout.write(encoded)
        return
    path = Path(output)
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing symlinked output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(encoded)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON file or - for stdin")
    parser.add_argument("--output", required=True, help="JSON file or - for stdout")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        value = json.loads(raw)
        write_receipt(normalize_receipt(value), args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
