# Installation

Use a tagged release for reproducibility. Verify `SHA256SUMS` before installing.

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
