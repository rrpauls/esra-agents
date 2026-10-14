# Oversight proposal 0009: Antigravity lifecycle hook hardening and install guidance

Status: proposed

## Decision

1. Make `runtime/esra_hook.py` natively output valid empty JSON (`{}`) to `stdout` when `--host antigravity`, fulfilling Antigravity's lifecycle hook output contract internally.
2. Clean up `hooks.json` command definitions by removing POSIX-only shell redirects and chained commands (`> /dev/null; echo '{}'`), ensuring cross-platform execution on both Unix and Windows hosts.
3. Update `INSTALL.md` and `AGENTS.md` to document direct Git clone installation paths (`~/.gemini/config/plugins/esra-agents` and `.agents/plugins/esra-agents`) alongside distribution ZIP and CLI workflows, clarifying native discovery of `hooks.json` and `plugin.json`.
4. Include `hooks.json` in `scripts/validate_plugin.py` forbidden lifecycle content inspection.
5. Add test coverage in `tests/test_adapters.py` verifying Antigravity hook stdout output contract.

## Bounds

This change improves reliability, cross-platform portability, and documentation for the Antigravity host integration. Observational lifecycle events, payload handling, privacy boundaries, and other host adapters (Claude, OpenAI, Hermes, Grok, OpenClaw) remain unchanged.

## Rollback

Revert the changes to `runtime/esra_hook.py`, `hooks.json`, `INSTALL.md`, `AGENTS.md`, and `tests/test_adapters.py`.
