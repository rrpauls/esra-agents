# 0004 — Privacy-bounded MCP evidence receipts

Status: accepted

## Context

ESRA host pilots and release checks can obtain useful evidence from MCP providers such as GitHub, Codex Security, browser verification, and Stack Overflow for Agents. Raw tool responses may contain prompts, tokens, account details, session identifiers, URLs with credentials, or unrelated payloads. Persisting those responses would violate the runtime privacy boundary.

## Decision

Add a dependency-free receipt normalizer at `runtime/mcp_evidence.py`. It accepts a small, caller-sanitized contract, rejects sensitive key names anywhere in the input, retains only explicit metadata fields, hashes evidence statements, and writes deterministic JSON with mode `0600`.

The normalizer is not an MCP client and does not grant network, account, or mutation authority. Host adapters remain responsible for calling read-only tools and constructing the bounded input. Raw MCP responses, prompts, transcripts, tool arguments/results, secrets, account identities, and session identifiers must never be passed through as evidence.

## Consequences

- Cross-host evidence can share one portable receipt format.
- Stored evidence proves only that a host adapter observed and summarized a result; it does not replace the provider's authoritative record.
- Human-readable evidence text is represented by SHA-256 digests, so a reviewer must retain the authoritative external record separately when reproducibility requires it.
- New providers require an explicit allowlist update and tests.
