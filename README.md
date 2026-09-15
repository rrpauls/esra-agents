# ESRA Agents

Portable ESRA 1.2 skills and a guarded evolutionary self-correction controller
for chat-scoped and autonomous agents.

This repository is the canonical implementation source for five selective ESRA
skills, evidence records, bounded experiments, audits, portable export, and thin
host adapters. The runtime-neutral specification remains at
https://github.com/rrpauls/esra.

## Design

- One open Agent Skills tree for every supported host.
- One dependency-free runtime, portable exporter, and guarded autonomous controller.
- Host-specific manifests, lifecycle event mappings, paths, and installers live
  only under `adapters/` and generated distributions.
- Routine work bypasses ESRA; focused skills work independently; a major change
  may receive at most one bounded review.

See [Architecture](docs/ARCHITECTURE.md), [runtime commands](docs/RUNTIME.md),
and [installation](INSTALL.md).

## Autonomous loop

The autonomous profile implements:

`observation → trigger → proposal → alignment → experiment → blind evaluation → local promotion → canary/rollback`

Guarded mode can promote only an exact evaluated revision of a local,
agent-owned, text-only skill. ESRA core, controller/evaluator code, values,
safety rules, credentials, runtime code, host configuration, and canonical
repository content remain human-approved proposals. Hooks persist only
allowlisted metadata and hashes; prompts, transcripts, tool arguments/results,
secrets, and raw run identifiers are excluded.

OpenClaw has a native TypeScript adapter at v0.2.1. Hermes has a native Python
plugin at v0.3.0. Stable autonomous capability remains gated by the shared host
gate and seven-day soak; a prerelease or passing package test is not that claim.

See [Architecture](docs/ARCHITECTURE.md), [controller commands](docs/RUNTIME.md),
[autonomous roadmap](docs/AUTONOMOUS_ROADMAP.md), [host-gate evidence](docs/AUTONOMOUS_HOST_GATE.md),
[installation](INSTALL.md), and the normative [Autonomous Agent Profile](https://github.com/rrpauls/esra/blob/main/docs/ESRA_Autonomous_Agent_Profile.md).

## Development

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 scripts/build_distributions.py
python3 scripts/validate_distributions.py
```

Licensed under Apache-2.0. See `NOTICE` for provenance and trademark separation.
