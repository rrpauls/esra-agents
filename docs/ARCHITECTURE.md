# Architecture

`esra-agents` implements ESRA 1.2 with a portable core and thin host adapters.

```text
skills/                 host-neutral procedural guidance
runtime/                exporter plus guarded autonomous controller
adapters/openai/        OpenAI lifecycle mapping and plugin extension
adapters/claude/        Claude Code manifest and lifecycle mapping
adapters/openclaw/      native OpenClaw hooks and Skill Workshop gate
adapters/hermes/        native Hermes plugin, installer, and legacy-name map
distributions/          generated host release artifacts
```

The specification remains in `rrpauls/esra`. A passing exporter benchmark
proves only the portable data contract. Native discovery, hooks, permissions,
and lifecycle behavior require current tests in each host.

The earlier `chatgpt-esra`, `claude-esra`, and `hermes-esra` repositories remain
available during migration. They are not silently replaced by this repository.

The controller is the policy boundary. Host adapters submit only normalized
events and exact candidate revisions. Host-native mutation remains outside the
ordinary agent identity: OpenClaw applies through Skill Workshop and an
`operator.admin` controller identity; Hermes applies through `skill_manage` in
an isolated evolution session. Both require a one-time token bound to the
evaluated controller revision and the host revision.

Operational events and budget records expire after 30 days. Promotion and
rollback receipts retain hashes, conclusions, and local evidence pointers.
Candidate content is local controller state and never transmitted by lifecycle
hooks; terminal candidate content and snapshots are purged after 30 days.
