# Oversight proposal 0007: root-level host hook discovery

Status: proposed

## Decision

Keep Antigravity's `hooks.json` and Claude Code's `.claude-plugin/plugin.json`
and `hooks/hooks.json` at their host-required root-relative discovery paths.
Treat these files as canonical and have distribution builds package them directly,
without duplicate copies under `adapters/`.

## Bounds

This relocates host discovery metadata only. Hook events, payloads, permissions,
and runtime behavior remain unchanged. OpenAI/Codex, Hermes, and OpenClaw retain
their existing adapter and plugin paths.

## Rollback

Restore the Antigravity and Claude files under their adapter directories and
update the distribution builder and validator to use those paths.
