# Oversight proposal 0001: universal core and host adapters

## Decision

Create `esra-agents` as the canonical implementation source for portable ESRA
skills, the dependency-free runtime, and host adapters for OpenAI, Claude Code,
and Hermes Agent.

Keep `rrpauls/esra` independent as the runtime-neutral specification and
conformance authority. Do not delete, rewrite, or deprecate the existing
`chatgpt-esra`, `claude-esra`, or `hermes-esra` repositories in this change.

## Evidence

- The five OpenAI and Claude skills implement the same selective ESRA workflow
  with only small host wording and runtime-path differences.
- Their portable exporters are materially identical apart from implementation
  identity and data-directory resolution.
- Native manifests, lifecycle hook payloads, environment variables, install
  paths, and release formats differ by host and must remain adapter concerns.
- Hermes also has legacy records and a different installed layout; compatibility
  belongs in its adapter rather than in portable skill instructions.

## Bounds

- One canonical `skills/` tree conforming to the open Agent Skills standard.
- One dependency-free Python runtime and one portable exporter.
- Thin adapters normalize host events and resolve host-specific state paths.
- Host distributions may contain different manifests and hooks, but must be
  generated from the same source revision.
- No automatic improvement cycle, persistent configuration mutation, skill
  promotion, or model modification.
- No prompt, transcript, tool input/output, secret, or raw session identifier in
  durable lifecycle records or portable exports.

## Verification

- Validate the portable and Codex plugin manifests.
- Validate every skill and its narrow activation boundary.
- Run core runtime, privacy, adapter, exporter, and deterministic packaging tests.
- Extract each distribution and test its expected structure.
- Run the upstream ESRA exporter benchmark against this implementation.
- Keep native-host maturity claims gated by the ESRA host pilot; package loading
  alone is not native lifecycle evidence.

## Rollback

The existing host repositories remain unchanged and usable. Until their release
flows are deliberately redirected, `esra-agents` is additive and can be rolled
back by removing or archiving only the new repository.
