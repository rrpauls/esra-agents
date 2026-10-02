#!/usr/bin/env python3
"""Synchronize checked-in metadata and matrices from VERSION and targets.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from .distribution_contract import ROOT, JSON_VERSIONS, matrix, version, validate_versions, validate_contract
except ImportError:
    from distribution_contract import ROOT, JSON_VERSIONS, matrix, version, validate_versions, validate_contract


def sync(root: Path = ROOT) -> None:
    release = version(root)
    for path, field in JSON_VERSIONS.items():
        file = root / path
        value = json.loads(file.read_text())
        value[field] = release
        file.write_text(json.dumps(value, indent=2) + "\n")
    path = root / "adapters/hermes/plugin/plugin.yaml"
    native = re.sub(r"^version: .+$", f"version: {release}", path.read_text(), flags=re.M)
    path.write_text(native)
    (root / "plugin.yaml").write_text(native)
    path = root / ".claude-plugin/marketplace.json"
    value = json.loads(path.read_text())
    value["metadata"]["version"] = release
    for entry in value["plugins"]:
        entry["version"] = release
    path.write_text(json.dumps(value, indent=2) + "\n")
    data = json.loads((root / "distributions/targets.json").read_text())
    block = "<!-- distribution-matrix:start -->\n" + matrix(data) + "<!-- distribution-matrix:end -->"
    for document in ("INSTALL.md", "README.md"):
        path = root / document
        text = path.read_text()
        if "<!-- distribution-matrix:start -->" in text:
            text = re.sub(r"<!-- distribution-matrix:start -->.*?<!-- distribution-matrix:end -->", block, text, flags=re.S)
        else:
            text += "\n" + block + "\n"
        path.write_text(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--stage-marketplace", type=Path,
                        help="Write isolated Codex/Claude catalogs; never changes user configuration")
    parser.add_argument("--channel", choices=("stable", "edge", "immutable"), default="stable")
    parser.add_argument("--ref", help="Required immutable version tag or full commit SHA")
    args = parser.parse_args()
    if args.stage_marketplace:
        selector = {"stable": "stable", "edge": "main"}.get(args.channel, args.ref)
        if args.channel == "immutable" and (not selector or not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?|[a-f0-9]{40}", selector)):
            parser.error("immutable channel requires --ref vX.Y.Z or a full commit SHA")
        from runtime.esra_paths import secure_dir, secure_open
        import os
        for relative in (".agents/plugins/marketplace.json", ".claude-plugin/marketplace.json"):
            value = json.loads((ROOT / relative).read_text())
            value["name"] = f"esra-agents-{args.channel}"
            value["plugins"][0]["source"]["ref"] = selector
            path = args.stage_marketplace / relative
            secure_dir(path.parent)
            with os.fdopen(secure_open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC), "w") as handle:
                handle.write(json.dumps(value, indent=2) + "\n")
        return 0
    if not args.check:
        sync()
    errors = validate_versions() + validate_contract()
    for error in errors:
        print(f"ERROR: {error}")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
