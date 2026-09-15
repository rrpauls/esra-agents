# Oversight proposal 0002: guarded autonomous controller

## Decision

Extend the portable ESRA implementation with a host-neutral controller and
native OpenClaw and Hermes adapters. The controller may autonomously observe,
propose, evaluate, promote, monitor, and roll back low-risk agent-owned skills.

## Evidence

- ESRA 1.2 defines self-correction, experimentation, integration, and audit, but
  the current shared runtime stops at recommendations and caller-run tests.
- OpenClaw exposes typed lifecycle and Skill Workshop proposal hooks.
- Hermes Agent exposes Python plugins, lifecycle hooks, scheduled agent turns,
  bundled skills, and the `skill_manage` surface.
- The legacy Hermes implementation contains useful trigger and rollback ideas,
  but its native lifecycle and real variant-execution claims remain unverified.

## Bounds

- Default mode is guarded and local-agent-only.
- Automatic promotion is limited to text-only agent-owned skills and routing
  metadata after deterministic checks, three comparable replays, and a blind
  baseline/candidate judgment.
- ESRA core, controller, evaluators, values, safety rules, credentials, runtime
  code, host configuration, and canonical repositories are proposal-only.
- One review, experiment, and promotion per agent per UTC day.
- Prompts, transcripts, tool arguments, tool output, secrets, and raw host
  identifiers are never persisted by the controller.
- ESRA-generated events cannot trigger another ESRA review.

## Verification

- Validate the normative autonomous schemas and fixtures.
- Exercise every controller transition, idempotency, budget, privacy, staging,
  canary, and rollback rule in isolated directories.
- Inspect both host plugins against their installed SDKs.
- Run the same ten-scenario autonomous host gate in temporary host profiles.
- Keep releases prerelease until native evidence exists; the seven-day soak is
  a stable-release gate and cannot be simulated.

## Rollback

Host plugins are opt-in. Disabling the plugin stops new observations and
reviews. Every promoted skill has an immutable pre-change snapshot and a
revision-bound rollback receipt. Existing v0.1.0 distributions remain usable.
