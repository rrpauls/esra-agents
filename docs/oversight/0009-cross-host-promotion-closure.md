# Oversight proposal 0009: close cross-host promotion claims with evidence

## Observed failure

A policy lesson was described as "fixed everywhere" after it was recorded in a single conversation's memory. No repository revisions, host installation, or consuming-agent discovery had been verified.

## Decision

Add a **guidance-level** target/propagation/verification checklist to the portable `esra-orchestrator` and `esra-reflection` skills and clarify the boundary in `docs/ARCHITECTURE.md`. Use `PROMOTED` only when every required target is verified; `PARTIAL` and `PENDING` are explicit non-success statuses. Preserve existing bounded, selective triggers and recursion suppression.

## Boundaries

- ESRA's autonomous local promotion controller and schemas do not gain cross-host write privileges.
- The skills do not install to any host or automatically synchronize conversations, packages, or release artifacts.
- Ordinary model/effort routing belongs to AI Orchestration, not to this review skill.
- Do not persist secrets, prompts, transcripts, or raw agent identifiers.

## Verification

- Existing portable-skill validation and selective routing tests remain intact.
- A small regression test checks that both portable skills reject unverified cross-host closure.
- Actual host installation or end-to-end consumption remains a separate pending validation.

## Rollback

Revert the guidance and regression check together if they conflict with verified host behavior. Keep any separate host distribution changes isolated.
