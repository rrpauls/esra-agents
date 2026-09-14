#!/usr/bin/env python3
"""Build and validate all ESRA host distribution archives."""

from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

try:
    from .build_distributions import build
except ImportError:
    from build_distributions import build

EXPECTED = {
    "esra-agents-marketplace.zip": {
        "esra-agents-marketplace/.agents/plugins/marketplace.json",
        "esra-agents-marketplace/plugins/esra-agents/.codex-plugin/plugin.json",
        "esra-agents-marketplace/plugins/esra-agents/plugin.json",
    },
    "esra-agents-claude.zip": {
        "esra-agents-claude/.claude-plugin/plugin.json",
        "esra-agents-claude/adapters/openai/hooks.json",
        "esra-agents-claude/hooks/hooks.json",
        "esra-agents-claude/runtime/esra_runtime.py",
    },
    "esra-agents-hermes.zip": {
        "esra-agents-hermes/install.sh",
        "esra-agents-hermes/adapters/openai/hooks.json",
        "esra-agents-hermes/adapters/hermes/adapter.json",
        "esra-agents-hermes/runtime/esra_runtime.py",
    },
}


def validate(directory: Path) -> list[str]:
    errors: list[str] = []
    for name, required in EXPECTED.items():
        path = directory / name
        if not path.is_file():
            errors.append(f"missing archive: {name}")
            continue
        try:
            with ZipFile(path) as archive:
                names = set(archive.namelist())
                missing = required - names
                errors.extend(f"{name}: missing {item}" for item in sorted(missing))
                if any("__pycache__" in item or item.endswith(".pyc") for item in names):
                    errors.append(f"{name}: contains Python cache artifacts")
                if any("build_distributions.py" in item for item in names):
                    errors.append(f"{name}: contains build tooling")
                bad = archive.testzip()
                if bad:
                    errors.append(f"{name}: corrupt member {bad}")
        except BadZipFile:
            errors.append(f"{name}: invalid ZIP")
    sums = directory / "SHA256SUMS"
    if not sums.is_file():
        errors.append("missing SHA256SUMS")
    else:
        for line in sums.read_text(encoding="utf-8").splitlines():
            expected, name = line.split("  ", 1)
            actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            if actual != expected:
                errors.append(f"checksum mismatch: {name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?")
    args = parser.parse_args()
    if args.directory:
        directory = Path(args.directory).resolve()
        errors = validate(directory)
    else:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            build(directory)
            errors = validate(directory)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Validated deterministic OpenAI, Claude, and Hermes distributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
