#!/usr/bin/env python3
"""Build and validate all ESRA host distribution archives."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import tempfile
from pathlib import Path
from zipfile import BadZipFile, ZipFile

try:
    from .build_distributions import ROOT, build
except ImportError:
    from build_distributions import ROOT, build

try:
    from .distribution_contract import contract, version
except ImportError:
    from distribution_contract import contract, version

EXPECTED = {
    name: {f"{value['root']}/{p}" if value["root"] else p for p in value["required_files"]}
    for name, value in contract()["artifacts"].items()
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


def validate_portable_skills(archive: ZipFile, *, claude: bool = False) -> list[str]:
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
                entrypoint = f"{name}/SKILL.md" if claude else "SKILL.md"
                if entrypoint not in names:
                    errors.append(f"{name}: missing root SKILL.md")
                elif skill.read(entrypoint) != source.read_bytes():
                    errors.append(f"portable ZIP differs from source: {name}")
                allowed = {"LICENSE", "NOTICE"} | {
                    path.relative_to(source.parent).as_posix()
                    for path in source.parent.rglob("*") if path.is_file()
                    and not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(source.parent).parts)
                    and path.suffix != ".pyc"
                }
                if claude:
                    allowed = {f"{name}/{p}" for p in allowed}
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


def validate_package(name: str, archive: ZipFile) -> list[str]:
    errors = []
    spec = contract()["artifacts"][name]
    root = spec["root"]
    names = set(archive.namelist())
    if name != "esra-agents-openai.zip" and any(not p.startswith(root + "/") for p in names):
        errors.append(f"{name}: plugin root has siblings")
    generic_roots = {p.rsplit("/", 1)[0] for p in names if p.endswith("/plugin.json")
                     and "/.codex-plugin/" not in p and "/.claude-plugin/" not in p}
    if generic_roots and generic_roots != {root}:
        errors.append(f"{name}: ambiguous plugin roots")
    def read(relative):
        return archive.read(f"{root}/{relative}")
    if read("VERSION").decode().strip() != version():
        errors.append(f"{name}: canonical version mismatch")
    for source in (ROOT / "skills").glob("*/SKILL.md"):
        relative = source.relative_to(ROOT).as_posix()
        if f"{root}/{relative}" not in names or read(relative) != source.read_bytes():
            errors.append(f"{name}: missing or altered canonical skill {source.parent.name}")
    for path in ("plugin.json", ".codex-plugin/plugin.json", ".claude-plugin/plugin.json", "package.json", "openclaw.plugin.json", "distribution.json"):
        if f"{root}/{path}" not in names:
            continue
        manifest = json.loads(read(path))
        if name == "esra-agents-antigravity.zip" and path == "plugin.json":
            if set(manifest) != {"name", "description"} or manifest["name"] != "esra-agents" or not isinstance(manifest["description"], str):
                errors.append("Antigravity native manifest violates closed schema")
        elif manifest.get("version") != version():
            errors.append(f"{name}: version drift in {path}")
        if path in {"plugin.json", ".codex-plugin/plugin.json"}:
            extension = manifest.get("extensions", {}).get("com.openai", manifest)
            hooks = extension.get("hooks")
            if hooks and (not isinstance(hooks, str) or not hooks.startswith("./") or f"{root}/{hooks[2:]}" not in names):
                errors.append(f"{name}: unresolved hook reference")
    if name == "esra-agents-hermes.zip":
        if f"version: {version()}\n" not in read("plugin.yaml").decode():
            errors.append("Hermes manifest version drift")
    if name == "esra-agents-claude.zip":
        market = json.loads(read(".claude-plugin/marketplace.json"))
        if market["metadata"]["version"] != version() or market["plugins"][0]["version"] != version():
            errors.append("Claude archive marketplace version drift")
        if "${CLAUDE_PLUGIN_ROOT}/runtime/esra_hook.py" not in read("hooks/hooks.json").decode():
            errors.append("Claude archive hooks do not resolve from the plugin root")
    if spec["kind"] == "web":
        allowed = {"plugin.json", ".codex-plugin/plugin.json", "VERSION", "LICENSE", "NOTICE", "INSTALL.md"}
        if any(p[len(root)+1:] not in allowed and not p[len(root)+1:].startswith("skills/") for p in names):
            errors.append("web package contains runtime/hooks or unexpected files")
        for path in ("plugin.json", ".codex-plugin/plugin.json"):
            manifest = json.loads(read(path))
            extension = manifest.get("extensions", {}).get("com.openai", manifest)
            if "hooks" in extension or "apps" in extension or "Local automation" in extension.get("interface", {}).get("capabilities", []):
                errors.append("web manifest advertises local hooks/apps/runtime")
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
                if name in {"esra-agents-skills.zip", "esra-agents-claude-skills.zip"}:
                    errors.extend(validate_portable_skills(archive, claude="claude" in name))
                else:
                    errors.extend(validate_package(name, archive))
                if any("__pycache__" in item or item.endswith(".pyc") for item in names):
                    errors.append(f"{name}: contains Python cache artifacts")
                if any("build_distributions.py" in item for item in names):
                    errors.append(f"{name}: contains build tooling")
                bad = archive.testzip()
                if bad:
                    errors.append(f"{name}: corrupt member {bad}")
        except (BadZipFile, OSError, ValueError, KeyError, UnicodeDecodeError) as exc:
            errors.append(f"{name}: invalid package: {exc}")
    sums = directory / "SHA256SUMS"
    if not sums.is_file():
        errors.append("missing SHA256SUMS")
    else:
        files = {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file() and path.name != "SHA256SUMS"}
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
