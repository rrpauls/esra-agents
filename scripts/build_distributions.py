#!/usr/bin/env python3
"""Build deterministic OpenAI, Claude, and Hermes ESRA distributions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
COMMON_FILES = (
    "README.md", "INSTALL.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE",
    "NOTICE", "esra-conformance.json", "plugin.json",
)
COMMON_DIRECTORIES = ("skills", "runtime", "docs")


def info(name: str, executable: bool = False) -> ZipInfo:
    value = ZipInfo(name, date_time=FIXED_TIME)
    value.compress_type = ZIP_DEFLATED
    value.external_attr = (0o100755 if executable else 0o100644) << 16
    return value


def add(archive: ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    archive.writestr(info(name, executable), data)


def source_files() -> list[Path]:
    files = [ROOT / relative for relative in COMMON_FILES]
    files.append(ROOT / "adapters/openai/hooks.json")
    for directory in COMMON_DIRECTORIES:
        files.extend(
            path
            for path in (ROOT / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing distribution input: {missing[0]}")
    return sorted(set(files))


def build_marketplace(output: Path) -> None:
    archive_root = "esra-agents-marketplace"
    plugin_root = f"{archive_root}/plugins/esra-agents"
    marketplace = {
        "name": "esra-agents",
        "interface": {"displayName": "ESRA Agents"},
        "plugins": [{
            "name": "esra-agents",
            "source": {"source": "local", "path": "./plugins/esra-agents"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        }],
    }
    with ZipFile(output, "w") as archive:
        add(archive, f"{archive_root}/.agents/plugins/marketplace.json", (json.dumps(marketplace, indent=2) + "\n").encode())
        add(archive, f"{archive_root}/INSTALL.md", (ROOT / "INSTALL.md").read_bytes())
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{plugin_root}/{relative}", path.read_bytes(), path.suffix == ".py")
        for relative in (".codex-plugin/plugin.json",):
            path = ROOT / relative
            add(archive, f"{plugin_root}/{relative}", path.read_bytes())


def build_claude(output: Path) -> None:
    archive_root = "esra-agents-claude"
    with ZipFile(output, "w") as archive:
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{archive_root}/{relative}", path.read_bytes(), path.suffix == ".py")
        add(archive, f"{archive_root}/.claude-plugin/plugin.json", (ROOT / "adapters/claude/plugin.json").read_bytes())
        add(archive, f"{archive_root}/hooks/hooks.json", (ROOT / "adapters/claude/hooks.json").read_bytes())


def build_hermes(output: Path) -> None:
    archive_root = "esra-agents-hermes"
    with ZipFile(output, "w") as archive:
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{archive_root}/{relative}", path.read_bytes(), path.suffix == ".py")
        for relative in ("adapters/hermes/adapter.json", "adapters/hermes/legacy-skill-map.json"):
            path = ROOT / relative
            add(archive, f"{archive_root}/{relative}", path.read_bytes())
        add(archive, f"{archive_root}/install.sh", (ROOT / "adapters/hermes/install.sh").read_bytes(), True)


def build(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        output_dir / "esra-agents-marketplace.zip",
        output_dir / "esra-agents-claude.zip",
        output_dir / "esra-agents-hermes.zip",
    ]
    build_marketplace(outputs[0])
    build_claude(outputs[1])
    build_hermes(outputs[2])
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in outputs)
    (output_dir / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="dist")
    args = parser.parse_args()
    for path in build((ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)):
        print(path)


if __name__ == "__main__":
    main()
