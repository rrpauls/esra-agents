# Architecture

`esra-agents` implements ESRA 1.2 with a portable core and thin host adapters.

```text
skills/                 host-neutral procedural guidance
runtime/                shared dependency-free state and exporter logic
adapters/openai/        OpenAI lifecycle mapping and plugin extension
adapters/claude/        Claude Code manifest and lifecycle mapping
adapters/hermes/        Hermes paths, installer, and legacy-name mapping
distributions/          generated host release artifacts
```

The specification remains in `rrpauls/esra`. A passing exporter benchmark
proves only the portable data contract. Native discovery, hooks, permissions,
and lifecycle behavior require current tests in each host.

The earlier `chatgpt-esra`, `claude-esra`, and `hermes-esra` repositories remain
available during migration. They are not silently replaced by this repository.
