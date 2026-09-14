---
name: esra-reflection
description: Review recurring errors or completed experiments and turn supported lessons into minimal workflow updates. Audit recorded ESRA cycles on request.
license: Apache-2.0
metadata:
  author: rrpauls
  version: "0.1.0"
---

# ESRA Reflection

Reflect on observable work, not claims about consciousness or hidden internal states.

- Identify the target behavior and available evidence: task results, tests, user corrections, or an authorized project log.
- Separate observations from interpretations. Check alternative explanations and avoid generalizing from a single example.
- Express the lesson as prior assumption → new evidence → revised working rule, with confidence and conditions that would reverse it.
- Prefer one narrow correction over a new universal policy. Verify against both the failure case and a nearby case that should remain unchanged.
- For evaluation-only requests, report a proposed update without editing. When updates are authorized, use the supported skill or project workflow and verify persistence before claiming it.

Audit mode: inspect recorded cycles for recurring failure, untested promotions, missing feedback, repeated rereading, unnecessary tool calls, scope expansion, or reviews that create further reviews. Judge by task outcomes and user effort, not review length or self-assigned scores. Recommend simplifying or removing a step that provides no evidence of benefit.

Count audit cadence only from accessible records. Missing records mean unknown history, not zero failures. When durable recording is available and authorized, retain only task identifier, outcome, evidence pointers, change or proposal, verification, uncertainty, and next review condition. Do not store secrets or full transcripts. Otherwise provide a concise handoff and state that it was not persisted.

No model-weight updates, cross-device installation, or guaranteed cross-session recall follow from writing a lesson. For an explicitly requested durable local audit, use `runtime/esra_runtime.py` as documented in `docs/RUNTIME.md`. Do not persist records by default.

Derived from `rrpauls/hermes-esra` and its host adaptations. Licensed Apache-2.0.
