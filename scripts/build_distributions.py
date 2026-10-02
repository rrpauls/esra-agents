#!/usr/bin/env python3
"""Build deterministic host plugins and universal portable skill bundles."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
from contextlib import contextmanager
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.esra_paths import refuse_symlink, secure_dir, secure_open  # noqa: E402
from scripts.distribution_contract import contract, version, validate_versions  # noqa: E402
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
COMMON_FILES = (
    "README.md", "INSTALL.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE",
    "NOTICE", "esra-conformance.json", "plugin.json", "VERSION",
)
COMMON_DIRECTORIES = ("skills", "runtime", "docs")


def info(name: str, executable: bool = False) -> ZipInfo:
    value = ZipInfo(name, date_time=FIXED_TIME)
    value.compress_type = ZIP_DEFLATED
    value.external_attr = (0o100755 if executable else 0o100644) << 16
    return value


def add(archive: ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    from runtime.esra_controller import safe_relative
    safe_relative(name)
    if name in archive.namelist():
        raise ValueError(f"duplicate distribution member: {name}")
    archive.writestr(info(name, executable), data)


def read_source(path: Path) -> bytes:
    with os.fdopen(secure_open(path, os.O_RDONLY), "rb") as handle:
        return handle.read()


@contextmanager
def output_archive(output: Path):
    with os.fdopen(secure_open(output, os.O_RDWR | os.O_CREAT | os.O_TRUNC), "w+b") as handle:
        with ZipFile(handle, "w") as archive:
            yield archive


def source_files() -> list[Path]:
    files = [ROOT / relative for relative in COMMON_FILES]
    files.append(ROOT / "adapters/openai/hooks.json")
    for directory in COMMON_DIRECTORIES:
        refuse_symlink(ROOT / directory)
        for path in (ROOT / directory).rglob("*"):
            refuse_symlink(path)
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files.append(path)
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing distribution input: {missing[0]}")
    return sorted(set(files))


def build_openai(output: Path) -> None:
    archive_root = "esra-agents-openai"
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
    with output_archive(output) as archive:
        add(archive, f"{archive_root}/.agents/plugins/marketplace.json", (json.dumps(marketplace, indent=2) + "\n").encode())
        add(archive, f"{archive_root}/INSTALL.md", read_source(ROOT / "INSTALL.md"))
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{plugin_root}/{relative}", read_source(path), path.suffix == ".py")
        for relative in (".codex-plugin/plugin.json",):
            path = ROOT / relative
            add(archive, f"{plugin_root}/{relative}", read_source(path))


def build_claude(output: Path) -> None:
    archive_root = "esra-agents-claude"
    with output_archive(output) as archive:
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{archive_root}/{relative}", read_source(path), path.suffix == ".py")
        add(archive, f"{archive_root}/.claude-plugin/plugin.json", read_source(ROOT / ".claude-plugin/plugin.json"))
        add(archive, f"{archive_root}/.claude-plugin/marketplace.json", read_source(ROOT / ".claude-plugin/marketplace.json"))
        add(archive, f"{archive_root}/hooks/hooks.json", read_source(ROOT / "hooks/hooks.json"))


def build_hermes(output: Path) -> None:
    archive_root = "esra-agents-hermes"
    with output_archive(output) as archive:
        native_sources = [
            path for path in source_files()
            if path.name != "plugin.json" and "adapters/openai" not in path.as_posix()
        ]
        for path in native_sources:
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{archive_root}/{relative}", read_source(path), path.suffix == ".py")
        add(archive, f"{archive_root}/plugin.yaml", read_source(ROOT / "adapters/hermes/plugin/plugin.yaml"))
        add(archive, f"{archive_root}/__init__.py", read_source(ROOT / "adapters/hermes/plugin/__init__.py"))
        add(archive, f"{archive_root}/review_wakeup.py", read_source(ROOT / "adapters/hermes/plugin/review_wakeup.py"), True)
        for relative in ("adapters/hermes/adapter.json", "adapters/hermes/legacy-skill-map.json"):
            path = ROOT / relative
            add(archive, f"{archive_root}/{relative}", read_source(path))
        add(archive, f"{archive_root}/install.sh", read_source(ROOT / "adapters/hermes/install.sh"), True)


def build_openclaw(output: Path) -> None:
    archive_root = "esra-agents-openclaw"
    required = [
        ROOT / "VERSION",
        ROOT / "package.json",
        ROOT / "openclaw.plugin.json",
        ROOT / "plugin.json",
        ROOT / "LICENSE",
        ROOT / "NOTICE",
        ROOT / "README.md",
    ]
    for directory in ("adapters/openclaw", "adapters/openai", "runtime", "skills"):
        refuse_symlink(ROOT / directory)
        for path in (ROOT / directory).rglob("*"):
            refuse_symlink(path)
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                required.append(path)
    with output_archive(output) as archive:
        for path in sorted(required):
            relative = path.relative_to(ROOT).as_posix()
            add(archive, f"{archive_root}/{relative}", read_source(path), path.suffix == ".py")


def build_antigravity(output: Path) -> None:
    archive_root = "esra-agents-antigravity"
    with output_archive(output) as archive:
        for path in source_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative in {"plugin.json", "adapters/openai/hooks.json"}:
                continue
            add(archive, f"{archive_root}/{relative}", read_source(path), path.suffix == ".py")
        add(archive, f"{archive_root}/plugin.json", json_bytes({
            "name": "esra-agents", "description": "Five ESRA skills and observational lifecycle hooks."
        }))
        # Native schema has no version field; keep release metadata separate.
        add(archive, f"{archive_root}/distribution.json", json_bytes({"name": "esra-agents", "version": version()}))
        add(archive, f"{archive_root}/hooks.json", read_source(ROOT / "hooks.json"))


def build_portable_skills(output: Path, *, claude: bool = False) -> None:
    """Group uploadable skill ZIPs and Markdown in one release download."""
    files: dict[str, bytes] = {}
    for entrypoint in sorted((ROOT / "skills").glob("*/SKILL.md")):
        skill = entrypoint.parent
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            for path in sorted(skill.rglob("*")):
                refuse_symlink(path)
                relative = path.relative_to(skill)
                if not path.is_file() or any(part.startswith(".") or part == "__pycache__" for part in relative.parts) or path.suffix == ".pyc":
                    continue
                data = read_source(path)
                data.decode("utf-8")  # Web import bundle contains text only.
                add(archive, f"{skill.name}/{relative.as_posix()}" if claude else relative.as_posix(), data)
            for name in ("LICENSE", "NOTICE"):
                add(archive, f"{skill.name}/{name}" if claude else name, read_source(ROOT / name))
        files[f"zip/{skill.name}.zip"] = buffer.getvalue()
        files[f"markdown/{skill.name}.md"] = read_source(entrypoint)
    files["INSTALL.md"] = web_instructions("Claude Web" if claude else "Gemini / generic skills")
    files["LICENSE"] = read_source(ROOT / "LICENSE")
    files["NOTICE"] = read_source(ROOT / "NOTICE")
    checksums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    with output_archive(output) as archive:
        for name, data in sorted(files.items()):
            add(archive, name, data)
        add(archive, "SHA256SUMS", checksums.encode())


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2) + "\n").encode()


def web_instructions(surface: str) -> bytes:
    return (f"# {surface}\n\nExtract the bundle and upload individual skills from zip/. "
            "Claude ZIPs contain a skill directory; Gemini ZIPs contain SKILL.md at root. "
            "Raw Markdown is in markdown/. Verify inner SHA256SUMS first.\n\n"
            "These packages provide portable reasoning workflows only. No ESRA Python "
            "runtime, lifecycle hooks, filesystem persistence or autonomous controller "
            "is deployed. Runtime references in skills apply only when separately "
            "provisioned and authorized. Update by manual replacement; remove uploaded "
            "skills in the host's skills settings.\n").encode()


def build_openai_plugin(output: Path, *, web: bool = False) -> None:
    archive_root = "esra-agents-openai-web" if web else "esra-agents-openai-plugin"
    with output_archive(output) as archive:
        if not web:
            for path in source_files():
                relative = path.relative_to(ROOT).as_posix()
                add(archive, f"{archive_root}/{relative}", read_source(path), path.suffix == ".py")
        else:
            for path in source_files():
                relative = path.relative_to(ROOT).as_posix()
                if relative.startswith("skills/") or relative in {"VERSION", "LICENSE", "NOTICE"}:
                    add(archive, f"{archive_root}/{relative}", read_source(path))
            portable = json.loads(read_source(ROOT / "plugin.json"))
            portable["description"] = "Five portable ESRA reasoning workflows."
            extension = portable["extensions"]["com.openai"]
            extension.pop("hooks", None)
            extension["interface"]["longDescription"] = "Portable workflows; runtime references require separately provisioned execution."
            extension["interface"]["capabilities"] = ["Analysis"]
            add(archive, f"{archive_root}/plugin.json", json_bytes(portable))
            add(archive, f"{archive_root}/INSTALL.md", web_instructions("ChatGPT Web"))
        codex = json.loads(read_source(ROOT / ".codex-plugin/plugin.json"))
        if web:
            codex.pop("hooks", None)
            codex["description"] = "Five portable ESRA reasoning workflows."
            codex["interface"] = portable["extensions"]["com.openai"]["interface"]
        add(archive, f"{archive_root}/.codex-plugin/plugin.json", json_bytes(codex))


def build(output_dir: Path) -> list[Path]:
    errors = validate_versions()
    if errors:
        raise ValueError("; ".join(errors))
    secure_dir(output_dir)
    builders = {
        "esra-agents-openai.zip": build_openai,
        "esra-agents-openai-plugin.zip": build_openai_plugin,
        "esra-agents-openai-web.zip": lambda p: build_openai_plugin(p, web=True),
        "esra-agents-claude.zip": build_claude,
        "esra-agents-claude-skills.zip": lambda p: build_portable_skills(p, claude=True),
        "esra-agents-hermes.zip": build_hermes,
        "esra-agents-openclaw.zip": build_openclaw,
        "esra-agents-antigravity.zip": build_antigravity,
        "esra-agents-skills.zip": build_portable_skills,
    }
    if builders.keys() != contract()["artifacts"].keys():
        raise ValueError("distribution builders disagree with targets.json")
    outputs = []
    for name in sorted(builders):
        path = output_dir / name
        builders[name](path)
        outputs.append(path)
    checksums = "".join(f"{hashlib.sha256(read_source(path)).hexdigest()}  {path.name}\n" for path in outputs)
    with os.fdopen(secure_open(output_dir / "SHA256SUMS", os.O_WRONLY | os.O_CREAT | os.O_TRUNC), "w", encoding="utf-8") as handle:
        handle.write(checksums)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="dist")
    args = parser.parse_args()
    for path in build((ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)):
        print(path)


if __name__ == "__main__":
    main()
