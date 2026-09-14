---
name: esra-experiments
description: Design bounded tests of proposed workflow or architecture improvements with baselines and rollback. Not required for ordinary test execution.
license: Apache-2.0
metadata:
  author: rrpauls
  version: "0.1.0"
---

# ESRA Experiments

Turn an improvement claim into the smallest informative comparison.

1. Define the hypothesis and the user's desired outcome.
2. Record the baseline, candidate, success measure, failure guardrails, time or resource budget, and stopping rule before execution.
3. Check value alignment: usefulness, privacy, reliability, and the user's constraints. Block or redesign a conflicting experiment; lower priority alone is not a safeguard.
4. Choose a local fixture or isolated environment where possible. Establish rollback before changes. Live deployments, spending, external messages, or destructive actions require the relevant authorization; permission to design an experiment is not permission to run it.
5. Keep model, task inputs, tool access, and evaluation criteria comparable. Change one variable where feasible; report confounders and inconclusive results.
6. Compare outcomes and choose adopt, revise, reject, or gather more evidence. A small successful trial is not proof of broad superiority.

For skill evaluation, include routine non-trigger tasks, ambiguous requests, missing tools, repeated failures, and requests that allow analysis but not edits. Prefer observable outcomes over matching wording.

For efficiency comparisons, report input, cached input if exposed, output, reasoning if exposed, tool calls, elapsed time, and task quality separately. File-size token estimates are not measured billing or quota usage. Do not promise a percentage improvement without comparative results.

Do not automatically promote skills or launch follow-up experiments. Close at the declared stopping rule. If the user asks to execute and persist a local command comparison, use `runtime/esra_runtime.py` as documented in `docs/RUNTIME.md`; preserve the same authorization, guardrail, and rollback boundaries.

Derived from `rrpauls/hermes-esra` and its host adaptations. Licensed Apache-2.0.
