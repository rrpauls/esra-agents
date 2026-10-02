#!/usr/bin/env python3
"""Silent, non-steering lifecycle adapter for supported ESRA hosts."""

from __future__ import annotations

import argparse
import json
import os
import sys

from esra_runtime import record_lifecycle, resolve_data_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", choices=("openai", "claude", "grok", "hermes", "antigravity"), required=True)
    parser.add_argument("--data-dir")
    parser.add_argument("--event", help="Override event name (useful for Antigravity)")
    try:
        args = parser.parse_args(argv)
        if args.host == "claude" and os.environ.get("GROK_PLUGIN_ROOT"):
            args.host = "grok"
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            return 0
        if args.event:
            payload["hook_event_name"] = args.event
        record_lifecycle(payload, args.host, resolve_data_dir(args.host, args.data_dir))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
