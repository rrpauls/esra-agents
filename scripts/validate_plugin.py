#!/usr/bin/env python3
"""Validate portable, Codex, Claude, and Hermes adapter contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from .distribution_contract import version, validate_versions, validate_contract
except ImportError:
    from distribution_contract import version, validate_versions, validate_contract


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = validate_versions() + validate_contract()
    portable = read("plugin.json")
    codex = read(".codex-plugin/plugin.json")
    claude = read(".claude-plugin/plugin.json")
    conformance = read("esra-conformance.json")
    marketplace = read(".agents/plugins/marketplace.json")
    versions = {portable.get("version"), codex.get("version"), claude.get("version"), conformance.get("implementation_version")}
    if versions != {version()}:
        errors.append(f"version drift across manifests: {sorted(str(value) for value in versions)}")
    if portable.get("$schema") != "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json":
        errors.append("plugin.json does not target Agent Plugins 1.0.0")
    if portable.get("name") != "esra-agents" or codex.get("name") != "esra-agents" or claude.get("name") != "esra-agents":
        errors.append("all plugin manifests must use the esra-agents name")
    if codex.get("skills") != "./skills/":
        errors.append("Codex compatibility manifest must expose ./skills/")
    entry = marketplace.get("plugins", [{}])[0]
    if marketplace.get("name") != "esra-agents" or entry.get("name") != "esra-agents":
        errors.append("repository marketplace must publish esra-agents")
    if entry.get("source", {}).get("ref") != "stable":
        errors.append("repository marketplace must follow the stable channel")
    extension = portable.get("extensions", {}).get("com.openai", {})
    hook_path = str(extension.get("hooks", "")).removeprefix("./")
    if not hook_path or not (ROOT / hook_path).is_file():
        errors.append("OpenAI extension hook path is unresolved")
    for relative in ("adapters/openai/hooks.json", "hooks/hooks.json"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        json.loads(text)
        for forbidden in ("prompt_text", "transcript_path", "tool_input", "tool_output", "$prompt"):
            if forbidden in text.lower():
                errors.append(f"{relative} mentions forbidden lifecycle content: {forbidden}")
    hermes = read("adapters/hermes/adapter.json")
    if hermes.get("native_lifecycle_hook") is not True:
        errors.append("Hermes adapter must declare its native lifecycle hook")
    openclaw = read("openclaw.plugin.json")
    package = read("package.json")
    if openclaw.get("id") != "esra-agents" or openclaw.get("version") != version():
        errors.append("OpenClaw manifest must identify esra-agents at the canonical version")
    if package.get("openclaw", {}).get("extensions") != ["./adapters/openclaw/src/index.ts"]:
        errors.append("package.json must expose the native OpenClaw entry")
    # Root-level hook and manifest files are the single canonical source for Antigravity and Claude Code.
    for path, label in (("hooks.json", "Antigravity"), ("hooks/hooks.json", "Claude Code"), (".claude-plugin/plugin.json", "Claude Code")):
        if not (ROOT / path).is_file():
            errors.append(f"missing {label} root hook/manifest: {path}")
    return errors


def main() -> int:
    try:
        errors = validate()
    except (OSError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Validated canonical versions, surface contracts, manifests and hook resources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
