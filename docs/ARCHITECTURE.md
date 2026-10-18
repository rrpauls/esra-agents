# Architecture

`esra-agents` implements ESRA 1.2 with a portable core and thin host adapters.

```text
skills/                 host-neutral procedural guidance
runtime/                exporter plus guarded autonomous controller
adapters/openai/        OpenAI lifecycle mapping and plugin extension
.claude-plugin/plugin.json, hooks/hooks.json
                        Claude Code manifest and lifecycle mapping
hooks.json              Antigravity lifecycle mapping
adapters/openclaw/      native OpenClaw hooks and Skill Workshop gate
adapters/hermes/        native Hermes plugin, installer, and legacy-name map
distributions/          generated host release artifacts
```

## Improvement propagation boundary

The [ESRA Promotion and Propagation Closure](https://github.com/rrpauls/esra/blob/main/docs/ESRA_Promotion_Closure.md)
requires a target manifest and evidence for each required consuming host before
claiming a workflow improvement is deployed. The portable skills
`esra-orchestrator` and `esra-reflection` provide guidance only; they do not
perform file installation or synchronize memory, host adapters, or releases.
Existing revision-bound local controller receipts remain local evidence; they
do not assert cross-host rollout. Record `PENDING`/`PARTIAL` honestly when
access, authorization, or installation verification is missing. Host distribution
and synchronization must be performed and tested separately.

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


## Distribution contracts and source channels

VERSION drives synchronized host metadata. distributions/targets.json drives
artifact contracts and generated documentation matrices. The existing canonical
root Claude hooks and Antigravity hooks are preserved; Antigravity's native
manifest is generated separately because its closed schema rejects portable
identity/version/extensions. Hermes Git discovery delegates to its native adapter.
The OpenClaw adapter and Python controller share declarative rejection policy in
runtime/review-policy.txt. Those expressions reject candidate text, never execute it.

Managed updates belong to hosts: stable moves only after release acceptance,
main is edge, and tags/SHAs remain immutable. ZIPs remain deterministic and
checksummed. Web artifacts omit runtime/hooks. Documentation and conformance
record package validation separately from actual host execution and soak gates.
