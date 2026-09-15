# Installation

Use a tagged release for reproducibility. Verify `SHA256SUMS` before installing.

## OpenClaw 2026.9.1

```bash
openclaw plugins install --force --accept-capabilities git:github.com/rrpauls/esra-agents@v0.2.2
openclaw plugins enable --accept-capabilities esra-agents
openclaw config set plugins.entries.esra-agents.hooks.allowConversationAccess true
openclaw gateway restart
openclaw plugins inspect esra-agents --runtime --json
```

`--force` acknowledges that the Git source is outside ClawHub trust metadata.
Grant `operator.admin` only to the separate controller identity that invokes
`skills.proposals.apply`, never to the ordinary agent.

## ChatGPT and Codex

Extract `esra-agents-marketplace.zip`, then add its marketplace root and plugin:

```bash
codex plugin marketplace add /absolute/path/to/esra-agents-marketplace
codex plugin add esra-agents@esra-agents
```

The portable repository root also follows Agent Plugins 1.0 and can be imported
by compatible local clients. Web-only clients do not receive local Python hooks
or filesystem persistence.

## Claude Code

Extract `esra-agents-claude.zip` and validate or load the extracted directory:

```bash
claude plugin validate --strict /absolute/path/to/esra-agents-claude
claude --plugin-dir /absolute/path/to/esra-agents-claude
```

## Hermes Agent

Extract `esra-agents-hermes.zip`, review the installer, then run:

```bash
cd /absolute/path/to/esra-agents-hermes
./install.sh
```

The installer respects `HERMES_HOME` and `ESRA_HOME`. Existing skill directories
are moved to sibling `.pre-esra-agents` backups; the installer refuses to
overwrite an existing backup.
