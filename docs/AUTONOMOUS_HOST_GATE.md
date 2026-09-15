# Autonomous host gate

Status: 15 September 2026

All host checks use isolated temporary state roots. Existing OpenClaw and Hermes profiles, gateways, and skills are not changed.

| Scenario | Shared controller | OpenClaw 2026.9.1 | Hermes 0.21.0 |
|---|---|---|---|
| Routine task does not review | Passed | Passed by observer/controller tests | Passed by observer/controller tests |
| Repeated failure queues one proposal review | Passed | Passed by durable queue tests | Passed by durable queue tests |
| Evidence excludes secrets and raw identifiers | Passed | Passed by hook allowlist inspection | Passed by native hook test |
| Unsafe candidate is blocked | Passed | Passed in real Workshop evaluation | Passed in controller/plugin tests |
| Good candidate wins three replays and applies locally | Passed | Passed through real `skills.proposals.apply` | Passed through native `skill_manage` integration test; real model-backed cron session pending |
| ESRA core remains human-pending | Passed | Passed | Passed |
| Stale revision is rejected | Passed | Passed by Workshop revision binding | Passed by controller token binding |
| Post-promotion regression rolls back | Passed | Passed with real Workshop-created local skill | Passed in isolated plugin/controller integration test |
| ESRA activity cannot trigger another cycle | Passed | Passed | Passed |
| Restart does not duplicate an interrupted apply | Passed | Passed by receipt-recovery test | Passed by shared receipt-recovery test |

OpenClaw runtime evidence observed in an isolated `OPENCLAW_STATE_DIR`: seven registered native hooks, clean runtime inspection, a scanner-blocked protected candidate, a scanner-clean candidate, exact authenticated apply, one-time authorization rejection on reuse, and canary rollback to an absent snapshot.

Hermes runtime evidence observed in an isolated `HERMES_HOME`: native plugin doctor passed with one tool and four hooks; five skills registered; nightly and event jobs were stored with only `esra` and `skills` toolsets; the event job reached the scheduler. The fresh agent run stopped because the isolated profile intentionally had no model or credentials. Therefore Hermes `v0.3.0` is not released yet.
