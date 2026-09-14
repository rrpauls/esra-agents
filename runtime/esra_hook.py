#!/usr/bin/env python3
"""Silent, non-steering lifecycle adapter for supported ESRA hosts."""

from __future__ import annotations

import argparse
import json
import sys

from esra_runtime import record_lifecycle, resolve_data_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", choices=("openai", "claude", "hermes"), required=True)
    parser.add_argument("--data-dir")
    try:
        args = parser.parse_args(argv)
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            return 0
        record_lifecycle(payload, args.host, resolve_data_dir(args.host, args.data_dir))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
