"""Dependency-free canonical version and distribution contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_VERSIONS = {
    "plugin.json": "version",
    ".codex-plugin/plugin.json": "version",
    ".claude-plugin/plugin.json": "version",
    "package.json": "version",
    "openclaw.plugin.json": "version",
    "esra-conformance.json": "implementation_version",
}


def version(root: Path = ROOT) -> str:
    value = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", value):
        raise ValueError("VERSION must be a semantic release version")
    return value


def contract(root: Path = ROOT) -> dict:
    return json.loads((root / "distributions/targets.json").read_text(encoding="utf-8"))


def validate_versions(root: Path = ROOT) -> list[str]:
    expected = version(root)
    errors = []
    for path, field in JSON_VERSIONS.items():
        if json.loads((root / path).read_text())[field] != expected:
            errors.append(f"{path}: version disagrees with VERSION ({expected})")
    for path in ("plugin.yaml", "adapters/hermes/plugin/plugin.yaml"):
        values = re.findall(r"^version: (.+)$", (root / path).read_text(), re.M)
        if values != [expected]:
            errors.append(f"{path}: version disagrees with VERSION")
    marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text())
    if marketplace["metadata"]["version"] != expected or any(
        p.get("version") != expected for p in marketplace["plugins"]
    ):
        errors.append("Claude marketplace version drift")
    return errors


def matrix(data: dict | None = None) -> str:
    data = data or contract()
    lines = ["<!-- Generated from distributions/targets.json; do not edit. -->",
             "| Host / surface | Install modes (preferred first) | Stable / edge updates | Hooks | Runtime | Verification |",
             "|---|---|---|---|---|---|"]
    for target in data["targets"]:
        modes = [target["preferred_installation_mode"]] + [
            m for m in target["installation_modes"] if m != target["preferred_installation_mode"]]
        lines.append(f'| {target["host"]} / {target["surface"]} | {", ".join(modes)} | '
                     f'{target["stable_update_mode"]} / {target["edge_update_mode"]} | '
                     f'{target["hook_capability"]} | {target["runtime_capability"]} | '
                     f'{target["verification_status"]} |')
    return "\n".join(lines) + "\n"


def validate_contract(root: Path = ROOT) -> list[str]:
    data = contract(root)
    errors = []
    modes = {"automatic", "automatic-opt-in", "manual-native", "manual-replace", "pinned", "unsupported"}
    required = {"id", "host", "surface", "artifact", "installation_modes", "preferred_installation_mode",
                "stable_update_mode", "edge_update_mode", "immutable_install_mode", "hook_capability",
                "runtime_capability", "required_manifest", "external_publication_requirement",
                "verification_status", "sources", "immutable_update_mode", "archive_update_mode"}
    ids = set()
    for target in data["targets"]:
        label = target.get("id", "unknown")
        if required - target.keys():
            errors.append(f"{label}: missing capability fields")
            continue
        if label in ids:
            errors.append(f"duplicate target: {label}")
        ids.add(label)
        if target["artifact"] not in data["artifacts"]:
            errors.append(f"{label}: unknown artifact")
        if target["preferred_installation_mode"] not in target["installation_modes"]:
            errors.append(f"{label}: preferred mode not supported")
        if any(target[k] not in modes for k in ("stable_update_mode", "edge_update_mode")):
            errors.append(f"{label}: invalid update mode")
        if target["hook_capability"] not in {"native", "runtime-dependent", "none"}:
            errors.append(f"{label}: invalid hook capability")
        if target["runtime_capability"] not in {"local", "environment-dependent", "none"}:
            errors.append(f"{label}: invalid runtime capability")
        if target["immutable_update_mode"] != "pinned" or target["archive_update_mode"] != "manual-replace":
            errors.append(f"{label}: immutable/archive updates must not track moving sources")
        if target["runtime_capability"] == "none" and target["hook_capability"] != "none":
            errors.append(f"{label}: hooks require an execution runtime")
        if target["immutable_install_mode"] not in {"exact-commit", "tag-or-sha", "checksummed-release"}:
            errors.append(f"{label}: invalid immutable selector")
        if not target["sources"]:
            errors.append(f"{label}: missing verification sources")
    if data["channels"] != {"stable": "stable", "edge": "main", "immutable": "tag-or-sha"}:
        errors.append("invalid source channels")
    for document in ("INSTALL.md", "README.md"):
        text = (root / document).read_text()
        expected = "<!-- distribution-matrix:start -->\n" + matrix(data) + "<!-- distribution-matrix:end -->"
        if expected not in text:
            errors.append(f"{document}: generated capability matrix is stale")
    for name, artifact in data["artifacts"].items():
        from runtime.esra_controller import safe_relative
        try:
            safe_relative(name)
            if not name.endswith(".zip"):
                errors.append(f"{name}: artifact must be a ZIP")
            if artifact["root"]:
                safe_relative(artifact["root"])
            for required_file in artifact["required_files"]:
                safe_relative(required_file)
        except (ValueError, KeyError) as exc:
            errors.append(f"{name}: invalid artifact contract: {exc}")
    return errors
