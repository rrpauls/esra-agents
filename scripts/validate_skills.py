#!/usr/bin/env python3
"""Validate the portable ESRA Agent Skills tree without third-party packages."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
HOST_MARKERS = (".codex/", ".claude/", ".hermes/", "$PLUGIN_ROOT", "$CLAUDE_PLUGIN_ROOT", "$HERMES_HOME")


def scalar(block: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$", block)
    return match.group(1).strip().strip('"\'') if match else None


def validate(root: Path = SKILLS) -> list[str]:
    errors: list[str] = []
    directories = sorted(path for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
    if not directories:
        return [f"no skill directories found in {root}"]
    for directory in directories:
        skill = directory / "SKILL.md"
        if not skill.is_file():
            errors.append(f"{directory.name}: missing SKILL.md")
            continue
        text = skill.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            errors.append(f"{skill}: invalid frontmatter delimiters")
            continue
        block = match.group(1)
        name = scalar(block, "name")
        description = scalar(block, "description")
        license_name = scalar(block, "license")
        version = scalar(block, "version")
        if name != directory.name or not name or not NAME.fullmatch(name):
            errors.append(f"{skill}: name must match the lowercase hyphenated directory")
        if not description or len(description) > 1024:
            errors.append(f"{skill}: description must contain 1-1024 characters")
        if license_name != "Apache-2.0":
            errors.append(f"{skill}: license must be Apache-2.0")
        if version != "0.1.0":
            errors.append(f"{skill}: metadata.version must be 0.1.0")
        if len(text.splitlines()) > 500:
            errors.append(f"{skill}: must remain under 500 lines")
        for marker in HOST_MARKERS:
            if marker in text:
                errors.append(f"{skill}: host-specific marker is not portable: {marker}")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if "://" not in target and not (directory / target).resolve().is_file():
                errors.append(f"{skill}: unresolved relative link: {target}")
    return errors


def main() -> int:
    errors = validate()
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"Validated {len(list(SKILLS.iterdir()))} portable ESRA skills")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
