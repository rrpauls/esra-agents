---
name: esra-orchestrator
description: Run bounded ESRA reviews after major architecture or skill changes, repeated failures, or an explicit full-cycle request. Skip routine work.
license: Apache-2.0
metadata:
  author: rrpauls
  version: "0.1.0"
---

# ESRA Orchestrator

Apply ESRA as a task-scoped workflow, not a background service or model-training mechanism.

## Route by need

- Routine answers, simple edits, and successful ordinary tests: stop without an ESRA cycle.
- One difficult decision or hypothesis: use only the relevant focused skill.
- Major architecture or skill changes, repeated failures, or explicit full-cycle requests: run at most one bounded review after the primary task. Task length alone is not a trigger.
- An active incident takes priority over retrospective work.

## One cycle

1. Observe the actual result: tests, tool output, user feedback, and missing evidence. Separate completed work from proposals.
2. Orient around the user's objective, constraints, and the highest-impact mismatch.
3. Decide on at most two improvements with observable success criteria. Check scope and value alignment before experiments.
4. Act only within the current authorization. For an analysis request, propose changes; do not implement them. For implementation, verify the selected change and summarize the result.
5. Close with one lesson and the evidence needed to revisit it. If blocked or inconclusive, say so; do not manufacture progress.

Load only a specialist that is genuinely needed: `esra-decisions` for trade-offs, `esra-experiments` for comparisons, `esra-reflection` for evidence integration, or `esra-crisis` for incidents. Resolve names in the host's current catalog; if absent, apply the relevant step directly. Do not require all four, delegate by default, or invoke legacy host-specific skills.

## Bounds and persistence

Never let an ESRA review, log entry, or audit trigger another cycle. Allow one review per primary task; stop when evidence is exhausted or the agreed test budget is reached. Ask before expanding scope.

No host-specific paths, services, memory APIs, or automatic post-task hooks are assumed. A trigger recommendation is not an executed review. Use an existing authorized project record when available. Save only concise evidence-backed conclusions, not private deliberations, secrets, full transcripts, or invented emotional states.

Audit after 5–10 recorded significant cycles or an explicit request. Count only accessible completed records since the last audit; if history is missing, report the cadence as unknown. This is task-time review, not scheduling.

When the user explicitly requests durable local records, baseline metrics, trigger scoring, an experiment run, or an audit, use `runtime/esra_runtime.py` as documented in `docs/RUNTIME.md`. The runtime is optional; never block the reasoning workflow merely because it is unavailable.

Derived from `rrpauls/hermes-esra` and its host adaptations. Licensed Apache-2.0.
