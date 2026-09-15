#!/usr/bin/env python3
"""Validate portable, Codex, Claude, and Hermes adapter contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors: list[str] = []
    portable = read("plugin.json")
    codex = read(".codex-plugin/plugin.json")
    claude = read("adapters/claude/plugin.json")
    conformance = read("esra-conformance.json")
    marketplace = read(".agents/plugins/marketplace.json")
    versions = {portable.get("version"), codex.get("version"), claude.get("version"), conformance.get("implementation_version")}
    if versions != {"0.3.0"}:
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
    if entry.get("source", {}).get("ref") != "v0.2.1":
        errors.append("repository marketplace must retain the latest released tag v0.2.1 until the Hermes gate passes")
    extension = portable.get("extensions", {}).get("com.openai", {})
    hook_path = str(extension.get("hooks", "")).removeprefix("./")
    if not hook_path or not (ROOT / hook_path).is_file():
        errors.append("OpenAI extension hook path is unresolved")
    for relative in ("adapters/openai/hooks.json", "adapters/claude/hooks.json"):
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
    if openclaw.get("id") != "esra-agents" or openclaw.get("version") != "0.3.0":
        errors.append("OpenClaw manifest must identify esra-agents v0.3.0")
    if package.get("openclaw", {}).get("extensions") != ["./adapters/openclaw/src/index.ts"]:
        errors.append("package.json must expose the native OpenClaw entry")
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
    print("Validated portable plugin and three host adapters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
