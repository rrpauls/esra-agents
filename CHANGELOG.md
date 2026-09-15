# Changelog

## 0.3.0 — 2026-09-15 (unreleased prerelease candidate)

- Replace the legacy Hermes installer with a native Hermes 0.21 Python plugin.
- Register four lifecycle hooks, five native plugin ESRA skills, `/esra`, the
  `hermes esra` CLI, and a constrained controller tool.
- Apply approved candidates through Hermes `skill_manage` with a one-time token.

## 0.2.1 — 2026-09-15 (prerelease)

- Add the compiled JavaScript entry required for remote OpenClaw Git installs.
- Mark the host `openclaw` peer dependency optional to avoid a nested host install.

## 0.2.0 — 2026-09-15 (prerelease)

- Add the guarded autonomous controller, explicit state machine, daily budgets,
  private storage, revision-bound tokens, snapshots, canary, and rollback.
- Add a native OpenClaw 2026.9.1 plugin with seven sanitized/evaluation hooks.
- Add the OpenClaw release archive and isolated autonomous gate tests.

## 0.1.0 — 2026-09-15

- Establish one portable Agent Skills catalog for OpenAI, Claude Code, and
  Hermes Agent.
- Add a dependency-free shared runtime, privacy-allowlisted lifecycle adapter,
  and deterministic ESRA 1.2 exporter.
- Add thin host manifests and installation adapters.
- Add deterministic marketplace, Claude, and Hermes release distributions.
- Add structural, runtime, privacy, exporter, adapter, and packaging tests.
