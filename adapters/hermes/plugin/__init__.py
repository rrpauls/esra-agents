"""Native Hermes 0.21 plugin for guarded autonomous ESRA."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

PLUGIN_DIR = Path(__file__).resolve().parent
ROOT = PLUGIN_DIR if (PLUGIN_DIR / "runtime").is_dir() else Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.esra_controller import Controller, digest  # noqa: E402

logger = logging.getLogger(__name__)
PLUGIN_VERSION = "0.3.0"


def _state_dir(ctx) -> Path:
    configured = str(ctx.get_config("state_dir", default="") or "").strip()
    if configured:
        return Path(configured).expanduser()
    hermes_root = os.environ.get("HERMES_HOME")
    return Path(hermes_root).expanduser() / "esra-controller" if hermes_root else Path.home() / ".hermes" / "esra-controller"


def _agent_id(ctx) -> str:
    return str(ctx.get_config("agent_id", default="default") or "default")


def _controller(ctx) -> Controller:
    hermes_root = os.environ.get("HERMES_HOME")
    skills_root = Path(hermes_root).expanduser() / "skills" if hermes_root else Path.home() / ".hermes" / "skills"
    return Controller(_state_dir(ctx), skills_root)


def _observe(ctx, event: dict[str, Any], *, trigger: bool = False) -> None:
    try:
        controller = _controller(ctx)
        controller.ingest({"host": "hermes", "agent_id": _agent_id(ctx), **event})
        if trigger:
            controller.tick(_agent_id(ctx))
    except Exception as exc:  # observer hooks must never block Hermes
        logger.debug("ESRA observer ignored controller error: %s", exc)


def _post_tool_call(ctx, tool_name: str = "", status: str = "", duration_ms: int | None = None,
                    error_type: str | None = None, **_: Any) -> None:
    failed = status not in {"", "success", "ok", "completed"}
    _observe(ctx, {
        "event_type": "tool_call",
        "outcome": "failure" if failed else "success",
        "duration_ms": duration_ms,
        "error_class": error_type if failed else None,
        "failure_fingerprint": f"tool:{tool_name}:{error_type or 'error'}" if failed else None,
    }, trigger=failed)


def _post_llm_call(ctx, model: str = "", platform: str = "", **_: Any) -> None:
    _observe(ctx, {
        "event_type": "model_call",
        "outcome": "success",
        "substantial": True,
        "evidence_digest": digest({"model": model, "platform": platform}, 16),
    })


def _session_end(ctx, completed: bool = False, failed: bool = False,
                 interrupted: bool = False, **_: Any) -> None:
    unsuccessful = failed or interrupted or not completed
    _observe(ctx, {
        "event_type": "agent_end",
        "outcome": "failure" if unsuccessful else "success",
        "error_class": "interrupted" if interrupted else "session-failure" if failed else None,
        "failure_fingerprint": "session-end" if unsuccessful else None,
        "substantial": True,
    }, trigger=unsuccessful)


def _skill_lifecycle(ctx, action: str = "", skill_name: str = "", reused: bool = False,
                     reuse_after_patch: bool = False, **_: Any) -> None:
    _observe(ctx, {
        "event_type": f"skill_{action or 'lifecycle'}",
        "outcome": "success",
        "activated_skills": [skill_name] if skill_name else [],
        "evidence_digest": digest({"skill": skill_name, "action": action, "reused": reused,
                                   "reuse_after_patch": reuse_after_patch}, 16),
    })


def _apply_candidate(ctx, candidate_id: str, token: str) -> dict[str, Any]:
    controller = _controller(ctx)
    candidate = controller.load_candidate(candidate_id)
    revision = candidate["revision_hash"]
    controller.stage_external(candidate_id, revision)
    controller.consume_apply_token(token, candidate_id, revision)
    target = controller._target(candidate)
    operations: list[dict[str, Any]] = [{
        "name": candidate["target"],
        "action": "patch" if target.exists() else "create",
        "content": candidate["files"]["SKILL.md"],
    }]
    for relative, content in candidate["files"].items():
        if relative == "SKILL.md":
            continue
        operations.append({
            "name": candidate["target"], "action": "write_file",
            "file_path": relative, "file_content": content,
        })
    raw = ctx.dispatch_tool("skill_manage", {"operations": operations})
    try:
        result = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        result = {"success": False, "host_result": str(raw)}
    if result.get("success") is True:
        receipt = controller.complete_external(candidate_id, revision, f"hermes-promote:{candidate_id}:{revision}")
        return {"success": True, "receipt": receipt}
    return {"success": False, "state": "staged", "host_result": result,
            "message": "Hermes skill_manage did not commit; approval may still be pending."}


def _action(ctx, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    controller = _controller(ctx)
    if action == "status":
        return controller.status()
    if action == "audit":
        return controller.audit()
    if action == "pause":
        return controller.set_mode("paused")
    if action == "resume":
        return controller.set_mode("guarded")
    if action == "review":
        return controller.tick(_agent_id(ctx), nightly=bool(payload.get("nightly", False)))
    if action == "next_review":
        return controller.next_review(_agent_id(ctx))
    if action == "complete_review":
        return controller.complete_review(
            _agent_id(ctx), str(payload.get("correlation_id", "")),
            str(payload.get("outcome", "")), str(payload.get("evidence_hash", "")),
        )
    if action == "propose":
        proposal = dict(payload.get("proposal") or {})
        proposal["agent_id"] = _agent_id(ctx)
        return controller.propose(proposal)
    if action == "evaluate":
        return controller.evaluate(str(payload.get("candidate_id", "")), dict(payload.get("evaluation") or {}))
    if action == "issue_token":
        candidate_id = str(payload.get("candidate_id", ""))
        candidate = controller.load_candidate(candidate_id)
        return controller.issue_apply_token(candidate_id, candidate["revision_hash"], candidate["revision_hash"])
    if action == "rollback":
        candidate_id = str(payload.get("candidate_id", ""))
        return controller.rollback(candidate_id, f"hermes-rollback:{candidate_id}")
    if action == "apply":
        return _apply_candidate(ctx, str(payload.get("candidate_id", "")), str(payload.get("apply_token", "")))
    raise ValueError(f"unknown ESRA action: {action}")


def _tool_handler(ctx, args: dict[str, Any], **_: Any) -> str:
    try:
        result = _action(ctx, str(args.get("action", "status")), args)
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def _slash_handler(ctx, raw_args: str) -> str:
    parts = raw_args.strip().split()
    action = parts[0] if parts else "status"
    payload: dict[str, Any] = {}
    if action == "rollback" and len(parts) > 1:
        payload["candidate_id"] = parts[1]
    elif action == "apply" and len(parts) > 2:
        payload.update(candidate_id=parts[1], apply_token=parts[2])
    elif action == "review":
        payload["nightly"] = "--nightly" in parts[1:]
    try:
        return json.dumps(_action(ctx, action, payload), indent=2, ensure_ascii=False, sort_keys=True)
    except Exception as exc:
        return f"ESRA error: {exc}"


def _setup_cli(parser: argparse.ArgumentParser) -> None:
    subs = parser.add_subparsers(dest="esra_action")
    for name in ("status", "audit", "pause", "resume"):
        subs.add_parser(name)
    rollback = subs.add_parser("rollback")
    rollback.add_argument("candidate_id")
    review = subs.add_parser("review")
    review.add_argument("--nightly", action="store_true")
    install_cron = subs.add_parser("install-cron")
    install_cron.add_argument("--schedule", default="0 2 * * *")


def _install_cron(ctx, schedule: str) -> dict[str, Any]:
    hermes_root = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    scripts = hermes_root / "scripts"
    scripts.mkdir(mode=0o700, parents=True, exist_ok=True)
    wakeup = scripts / "esra-review-wakeup.py"
    shutil.copyfile(PLUGIN_DIR / "review_wakeup.py", wakeup)
    wakeup.chmod(0o700)
    prompt = (
        "Run one bounded guarded ESRA review. Call esra_controller next_review. "
        "If none is pending, stop. Inspect only hashes, local evidence pointers, and at most four "
        "reviewer-provided redacted excerpts. Use propose for an exact local agent-owned text skill "
        "candidate; never edit ESRA core, policy, runtime, credentials, or host configuration. "
        "Complete the queue item with complete_review. Do not review ESRA-generated activity."
    )
    nightly_args = {
        "action": "create", "name": "ESRA nightly review", "schedule": schedule,
        "prompt": prompt, "skills": ["esra-orchestrator"],
        "enabled_toolsets": ["esra", "skills"], "deliver": "local",
    }
    event_args = {
        "action": "create", "name": "ESRA event review", "schedule": "every 15m",
        "prompt": prompt, "monitor": str(wakeup),
        "skills": ["esra-orchestrator"],
        "enabled_toolsets": ["esra", "skills"], "deliver": "local",
    }
    try:
        from tools.cronjob_tools import cronjob

        nightly = cronjob(**nightly_args)
        direct_event = dict(event_args)
        direct_event["monitor_script"] = Path(str(direct_event.pop("monitor"))).name
        event = cronjob(**direct_event)
    except ImportError:
        # Lightweight test hosts may expose only the native dispatch surface.
        nightly = ctx.dispatch_tool("cronjob_manage", nightly_args)
        event = ctx.dispatch_tool("cronjob_manage", event_args)
    return {"nightly": json.loads(nightly), "event": json.loads(event), "wakeup_script": str(wakeup)}


def _cli_handler(ctx, args: argparse.Namespace) -> None:
    action = getattr(args, "esra_action", None) or "status"
    payload = vars(args)
    try:
        result = _install_cron(ctx, args.schedule) if action == "install-cron" else _action(ctx, action, payload)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        raise SystemExit(f"ESRA error: {exc}") from exc


ESRA_TOOL_SCHEMA = {
    "name": "esra_controller",
    "description": (
        "Inspect or operate the guarded local ESRA evolution controller. Routine tasks must not call "
        "this tool. Use it only in an explicit or queued ESRA review/evolution session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "audit", "review", "next_review", "complete_review", "propose", "evaluate", "issue_token", "apply", "rollback"]},
            "nightly": {"type": "boolean"},
            "candidate_id": {"type": "string"},
            "apply_token": {"type": "string"},
            "correlation_id": {"type": "string"},
            "outcome": {"type": "string"},
            "evidence_hash": {"type": "string"},
            "proposal": {"type": "object"},
            "evaluation": {"type": "object"},
        },
        "required": ["action"],
    },
}


def register(ctx) -> None:
    for skill_dir in sorted((ROOT / "skills").iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if skill_file.is_file():
            ctx.register_skill(skill_dir.name, skill_file)

    ctx.register_hook("post_tool_call", lambda **kwargs: _post_tool_call(ctx, **kwargs))
    ctx.register_hook("post_llm_call", lambda **kwargs: _post_llm_call(ctx, **kwargs))
    ctx.register_hook("on_session_end", lambda **kwargs: _session_end(ctx, **kwargs))
    ctx.register_hook("on_skill_lifecycle", lambda **kwargs: _skill_lifecycle(ctx, **kwargs))
    ctx.register_tool(
        name="esra_controller", toolset="esra", schema=ESRA_TOOL_SCHEMA,
        handler=lambda args, **kwargs: _tool_handler(ctx, args, **kwargs), emoji="🧬",
    )
    ctx.register_command(
        "esra", handler=lambda raw: _slash_handler(ctx, raw),
        description="Status, pause, resume, review, apply, or roll back guarded ESRA.",
        args_hint="[status|pause|resume|review|apply|rollback]",
    )
    ctx.register_cli_command(
        name="esra", help="Manage guarded autonomous ESRA", setup_fn=_setup_cli,
        handler_fn=lambda args: _cli_handler(ctx, args),
        description="Status, audit, pause, resume, review, or roll back guarded ESRA.",
    )
