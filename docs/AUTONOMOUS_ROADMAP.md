# Autonomous ESRA roadmap

Status: 15 September 2026

The shared controller implements the guarded loop:

`observation → trigger → proposal → alignment → experiment → blind evaluation → local promotion → canary/rollback`.

## Release sequence

- `v0.2.0` — OpenClaw prerelease. The isolated OpenClaw 2026.9.1 gate passed native plugin inspection, Workshop scanning, authenticated revision-bound apply, and automatic rollback.
- `v0.3.0` — Hermes prerelease candidate. The Hermes 0.21.0 package, four hooks, five bundled skills, controller tool, CLI, and two fresh-session cron definitions validate. Release remains blocked until an isolated model-backed native cron run and equivalent end-to-end apply/rollback gate pass.
- stable — blocked until both hosts complete a seven-day soak, at least 20 substantial tasks per host, a real promotion and verified rollback, and zero privacy or safety violations.

The canonical checklist and observed evidence are maintained in [AUTONOMOUS_HOST_GATE.md](AUTONOMOUS_HOST_GATE.md). Historical host-specific implementations are not competing runtimes.
