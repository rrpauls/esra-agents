#!/usr/bin/env python3
"""Build and validate all ESRA host distribution archives."""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import stat
import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

try:
    from .build_distributions import ROOT, build
except ImportError:
    from build_distributions import ROOT, build

EXPECTED = {
    "esra-agents-openai.zip": {
        "esra-agents-openai/.agents/plugins/marketplace.json",
        "esra-agents-openai/plugins/esra-agents/.codex-plugin/plugin.json",
        "esra-agents-openai/plugins/esra-agents/plugin.json",
    },
    "esra-agents-claude.zip": {
        "esra-agents-claude/.claude-plugin/plugin.json",
        "esra-agents-claude/adapters/openai/hooks.json",
        "esra-agents-claude/hooks/hooks.json",
        "esra-agents-claude/runtime/esra_runtime.py",
    },
    "esra-agents-hermes.zip": {
        "esra-agents-hermes/install.sh",
        "esra-agents-hermes/plugin.yaml",
        "esra-agents-hermes/__init__.py",
        "esra-agents-hermes/review_wakeup.py",
        "esra-agents-hermes/adapters/hermes/adapter.json",
        "esra-agents-hermes/runtime/esra_controller.py",
        "esra-agents-hermes/runtime/esra_runtime.py",
    },
    "esra-agents-openclaw.zip": {
        "esra-agents-openclaw/package.json",
        "esra-agents-openclaw/openclaw.plugin.json",
        "esra-agents-openclaw/adapters/openclaw/src/index.ts",
        "esra-agents-openclaw/runtime/esra_controller.py",
    },
    "esra-agents-antigravity.zip": {
        "esra-agents-antigravity/hooks.json",
        "esra-agents-antigravity/plugin.json",
        "esra-agents-antigravity/runtime/esra_runtime.py",
    },
    "esra-agents-skills.zip": {"INSTALL.md", "LICENSE", "NOTICE", "SHA256SUMS"},
}


def validate_members(archive: ZipFile) -> list[str]:
    errors = []
    names = set()
    for member in archive.infolist():
        name = member.filename
        parts = name.rstrip("/").split("/")
        if (name.startswith("/") or "\\" in name or ":" in name or "\x00" in name
                or any(part in {"", ".", ".."} or part.endswith((".", " ")) for part in parts)):
            errors.append(f"unsafe archive path: {name}")
        if stat.S_ISLNK(member.external_attr >> 16):
            errors.append(f"archive contains symlink: {name}")
        if name in names:
            errors.append(f"duplicate archive member: {name}")
        names.add(name)
    if sum(member.file_size for member in archive.infolist()) > 100 * 1024 * 1024:
        errors.append("archive exceeds 100 MB uncompressed limit")
    return errors


def check_checksums(manifest: str, files: dict[str, bytes]) -> list[str]:
    errors = []
    listed = set()
    for line in manifest.splitlines():
        digest, separator, name = line.partition("  ")
        if not separator or not re.fullmatch(r"[a-f0-9]{64}", digest) or name in listed or name not in files:
            errors.append(f"invalid checksum entry: {line}")
            continue
        listed.add(name)
        if hashlib.sha256(files[name]).hexdigest() != digest:
            errors.append(f"checksum mismatch: {name}")
    errors.extend(f"missing checksum: {name}" for name in sorted(files.keys() - listed))
    return errors


def validate_portable_skills(archive: ZipFile) -> list[str]:
    errors = []
    expected = {"INSTALL.md", "LICENSE", "NOTICE", "SHA256SUMS"}
    for source in sorted((ROOT / "skills").glob("*/SKILL.md")):
        name = source.parent.name
        zip_name, md_name = f"zip/{name}.zip", f"markdown/{name}.md"
        expected.update((zip_name, md_name))
        if md_name not in archive.namelist() or zip_name not in archive.namelist():
            errors.append(f"missing portable skill: {name}")
            continue
        if archive.read(md_name) != source.read_bytes():
            errors.append(f"portable Markdown differs from source: {name}")
        try:
            with ZipFile(io.BytesIO(archive.read(zip_name))) as skill:
                member_errors = validate_members(skill)
                if member_errors:
                    errors.extend(member_errors)
                    continue
                names = skill.namelist()
                if "SKILL.md" not in names:
                    errors.append(f"{name}: missing root SKILL.md")
                elif skill.read("SKILL.md") != source.read_bytes():
                    errors.append(f"portable ZIP differs from source: {name}")
                allowed = {"LICENSE", "NOTICE"} | {
                    path.relative_to(source.parent).as_posix()
                    for path in source.parent.rglob("*") if path.is_file()
                    and not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(source.parent).parts)
                    and path.suffix != ".pyc"
                }
                if set(names) != allowed or len(names) != len(set(names)):
                    errors.append(f"{name}: unexpected or missing skill files")
                if skill.testzip():
                    errors.append(f"{name}: corrupt skill ZIP")
                for member in names:
                    skill.read(member).decode("utf-8")
        except (BadZipFile, UnicodeDecodeError):
            errors.append(f"{name}: invalid skill ZIP or non-text content")
    if set(archive.namelist()) != expected:
        errors.append("portable bundle has unexpected or missing files")
    if "SHA256SUMS" in archive.namelist():
        files = {name: archive.read(name) for name in archive.namelist() if name != "SHA256SUMS"}
        errors.extend(check_checksums(archive.read("SHA256SUMS").decode(), files))
    return errors


def validate(directory: Path) -> list[str]:
    errors: list[str] = []
    for name, required in EXPECTED.items():
        path = directory / name
        if not path.is_file():
            errors.append(f"missing archive: {name}")
            continue
        try:
            with ZipFile(path) as archive:
                member_errors = validate_members(archive)
                if member_errors:
                    errors.extend(member_errors)
                    continue
                names = set(archive.namelist())
                missing = required - names
                errors.extend(f"{name}: missing {item}" for item in sorted(missing))
                if name == "esra-agents-skills.zip":
                    errors.extend(validate_portable_skills(archive))
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
        files = {name: (directory / name).read_bytes() for name in EXPECTED if (directory / name).is_file()}
        errors.extend(check_checksums(sums.read_text(encoding="utf-8"), files))
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
    print("Validated host plugin distributions and universal portable skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
