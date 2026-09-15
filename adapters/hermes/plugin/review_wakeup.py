#!/usr/bin/env python3
"""Cheap Hermes cron pre-check: wake only when the ESRA queue has pending work."""

import json
import os
from pathlib import Path


def main() -> None:
    root = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    queue = root / "esra-controller" / "review-queue.jsonl"
    latest = {}
    if queue.is_file() and not queue.is_symlink():
        for line in queue.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("correlation_id"):
                latest[row["correlation_id"]] = row
    pending = sorted(
        [
            {"correlation_id": row["correlation_id"], "reason": row.get("reason")}
            for row in latest.values() if row.get("status") == "pending"
        ],
        key=lambda row: row["correlation_id"],
    )
    print(json.dumps({"wakeAgent": bool(pending), "pending": pending}, sort_keys=True))


if __name__ == "__main__":
    main()
