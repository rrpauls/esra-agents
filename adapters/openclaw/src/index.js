import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const PLUGIN_VERSION = "0.3.0";
const CONTROLLER = resolve(dirname(fileURLToPath(import.meta.url)), "../../../runtime/esra_controller.py");
const FORBIDDEN = /(?:https?:\/\/|requires_env|api[_-]?key|credential|authorization:|install[_ -]?hook|rm\s+-rf|mkfs\b|shutdown\b|curl\b.*\|\s*(?:sh|bash)|wget\b.*\|\s*(?:sh|bash))/i;
const PROTECTED = /^(?:esra-|controller|evaluator|value|safety)/i;
function stringValue(value) {
    return typeof value === "string" && value.length > 0 ? value : undefined;
}
function settings(api) {
    const config = (api.pluginConfig ?? {});
    const stateBase = stringValue(config.stateDir)
        ?? join(process.env.OPENCLAW_STATE_DIR || join(homedir(), ".openclaw"), "esra-controller");
    return {
        stateDir: stateBase,
        python: stringValue(config.pythonPath) ?? "python3",
        agentId: stringValue(config.agentId) ?? "default",
    };
}
function controller(api, args, input, skillsRoot) {
    const config = settings(api);
    return new Promise((resolvePromise, reject) => {
        const rootArgs = skillsRoot ? ["--skills-root", skillsRoot] : [];
        const child = spawn(config.python, [CONTROLLER, "--state-dir", config.stateDir, ...rootArgs, ...args], {
            stdio: ["pipe", "pipe", "pipe"],
            env: process.env,
        });
        let stdout = "";
        let stderr = "";
        child.stdout.setEncoding("utf8");
        child.stderr.setEncoding("utf8");
        child.stdout.on("data", (chunk) => { stdout += chunk; });
        child.stderr.on("data", (chunk) => { stderr += chunk; });
        child.on("error", reject);
        child.on("close", (code) => {
            if (code !== 0) {
                reject(new Error(stderr.trim() || `ESRA controller exited ${code}`));
                return;
            }
            try {
                resolvePromise(JSON.parse(stdout));
            }
            catch (error) {
                reject(error);
            }
        });
        child.stdin.end(input ? JSON.stringify(input) : undefined);
    });
}
function agentId(api, ctx) {
    return stringValue(ctx.agentId) ?? settings(api).agentId;
}
async function ingest(api, ctx, event) {
    const payload = { host: "openclaw", agent_id: agentId(api, ctx), ...event };
    const workspaceDir = stringValue(ctx.workspaceDir);
    const skillsRoot = workspaceDir ? join(workspaceDir, "skills") : undefined;
    await controller(api, ["ingest"], payload, skillsRoot);
    if (payload.outcome === "failure" || payload.verifier_failure === true) {
        await controller(api, ["tick", "--agent", String(payload.agent_id)]);
    }
}
function staticFindings(event) {
    const findings = [];
    if (PROTECTED.test(event.skill?.name ?? "")) {
        findings.push({ ruleId: "esra.protected-target", severity: "critical", message: "ESRA core and policy targets require human approval." });
    }
    const files = [event.candidate?.skillMd, ...(event.candidate?.files ?? [])];
    for (const file of files) {
        if (!file || file.encoding !== "utf8" || typeof file.content !== "string") {
            findings.push({ ruleId: "esra.text-only", severity: "critical", message: "Guarded evolution accepts UTF-8 text only.", file: file?.path });
        }
        else if (FORBIDDEN.test(file.content)) {
            findings.push({ ruleId: "esra.authority-expansion", severity: "critical", message: "Candidate requests network, credential, install, or dangerous-command authority.", file: file.path });
        }
    }
    return findings;
}
export default {
    id: "esra-agents",
    name: "ESRA Autonomous Controller",
    version: PLUGIN_VERSION,
    register(api) {
        api.on("model_call_ended", async (event, ctx) => {
            await ingest(api, ctx, {
                event_type: "model_call",
                outcome: event.outcome === "error" ? "failure" : "success",
                duration_ms: event.durationMs,
                error_class: event.errorCategory ?? event.failureKind,
                failure_fingerprint: event.errorCategory ?? event.failureKind,
            });
        }, { registrationId: "esra-model-observer", timeoutMs: 5000 });
        api.on("after_tool_call", async (event, ctx) => {
            await ingest(api, ctx, {
                event_type: "tool_call",
                outcome: event.error ? "failure" : "success",
                duration_ms: event.durationMs,
                error_class: event.error ? "tool-error" : undefined,
                failure_fingerprint: event.error ? `tool:${event.toolName}` : undefined,
            });
        }, { registrationId: "esra-tool-observer", timeoutMs: 5000 });
        api.on("agent_end", async (event, ctx) => {
            await ingest(api, ctx, {
                event_type: "agent_end",
                outcome: event.success ? "success" : "failure",
                duration_ms: event.durationMs,
                error_class: event.success ? undefined : "agent-error",
                substantial: (event.durationMs ?? 0) >= 1000,
            });
        }, { registrationId: "esra-agent-observer", timeoutMs: 5000 });
        api.on("skill_proposal_evaluate", async (event, ctx) => {
            const findings = staticFindings(event);
            if (findings.length > 0) {
                return { evaluatorVersion: PLUGIN_VERSION, mode: "guarded", decision: "block", summary: "Guarded ESRA validation blocked this revision.", findings };
            }
            if (event.reason !== "apply") {
                return { evaluatorVersion: PLUGIN_VERSION, mode: "guarded", decision: "revise", summary: "Static validation passed; independent replay evaluation and a one-time apply token are still required." };
            }
            const token = stringValue(event.correlationId);
            if (!token) {
                return { evaluatorVersion: PLUGIN_VERSION, mode: "guarded", decision: "block", summary: "Missing revision-bound ESRA apply token." };
            }
            try {
                const workspaceDir = stringValue(ctx.workspaceDir);
                if (!workspaceDir)
                    throw new Error("missing workspace directory");
                await controller(api, ["stage-external", "--candidate", event.proposal.id], undefined, join(workspaceDir, "skills"));
                await controller(api, ["consume-token", "--candidate", event.proposal.id, "--host-revision", event.proposal.revisionSha256, "--token", token]);
                return { evaluatorVersion: PLUGIN_VERSION, mode: "guarded", decision: "pass", summary: "Exact revision authorized by a completed ESRA evaluation." };
            }
            catch {
                return { evaluatorVersion: PLUGIN_VERSION, mode: "guarded", decision: "block", summary: "Invalid, expired, stale, or consumed ESRA apply token." };
            }
        }, { registrationId: "esra-guarded-evaluator", timeoutMs: 10000 });
        api.on("skill_proposal_changed", async (event, ctx) => {
            if (event.action === "applied") {
                const workspaceDir = stringValue(ctx.workspaceDir);
                if (!workspaceDir)
                    throw new Error("missing workspace directory");
                const key = stringValue(event.correlationId) ?? `openclaw:${event.proposal.id}:${event.proposal.revisionSha256}`;
                await controller(api, ["complete-external", "--candidate", event.proposal.id, "--idempotency-key", key], undefined, join(workspaceDir, "skills"));
            }
            await ingest(api, ctx, {
                event_type: `skill_proposal_${event.action}`,
                outcome: event.action === "quarantined" || event.action === "stale" ? "failure" : "success",
                candidate_id: event.proposal?.id,
                evidence_digest: event.proposal?.revisionSha256,
            });
        }, { registrationId: "esra-proposal-observer", timeoutMs: 5000 });
        api.on("skill_changed", async (event, ctx) => {
            await ingest(api, ctx, {
                event_type: `skill_${event.action}`,
                outcome: "success",
                candidate_id: event.proposal?.id,
                evidence_digest: event.after?.revision?.treeSha256 ?? event.before?.revision?.treeSha256,
            });
        }, { registrationId: "esra-skill-observer", timeoutMs: 5000 });
        api.on("cron_changed", async (event) => {
            if (event.action !== "finished")
                return;
            const selectedAgent = stringValue(event.agentId) ?? settings(api).agentId;
            await ingest(api, { agentId: selectedAgent }, {
                event_type: "cron_finished",
                outcome: event.completionStatus === "failed" ? "failure" : "success",
                duration_ms: event.durationMs,
                error_class: event.completionStatus === "failed" ? "cron-error" : undefined,
            });
            if (event.job?.name === "ESRA nightly review") {
                await controller(api, ["tick", "--agent", selectedAgent, "--nightly"]);
            }
        }, { registrationId: "esra-cron-observer", timeoutMs: 5000 });
    },
};
