# Installation

Use a tagged release for reproducibility. Verify `SHA256SUMS` before installing.

## OpenClaw 2026.9.1

Install the v0.2.2 prerelease from GitHub, explicitly enable it, grant the
read-only `agent_end` hook access, and restart the Gateway:

```bash
openclaw plugins install --force --accept-capabilities git:github.com/rrpauls/esra-agents@v0.2.2
openclaw plugins enable --accept-capabilities esra-agents
openclaw config set plugins.entries.esra-agents.hooks.allowConversationAccess true
openclaw gateway restart
openclaw plugins inspect esra-agents --runtime --json
```

The plugin ignores the messages carried by `agent_end`; OpenClaw nevertheless
requires explicit conversation-access consent for every non-bundled subscriber
to that event. Omit that consent to run the remaining six sanitized hooks.
`--force` acknowledges that the Git source is outside ClawHub trust metadata.

Create a separate Gateway identity with `operator.admin` for the controller
that invokes `skills.proposals.apply`; do not grant that scope to the ordinary
agent. Skill Workshop owns proposal storage and the live write. Pass the
one-time revision-bound token returned by `esra_controller.py issue-token` as
the apply request's `correlationId`.

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

The v0.3.0 package installs a native Python plugin under
`$HERMES_HOME/plugins/esra-agents`; it refuses to overwrite an existing plugin.
The plugin registers the five bundled skills through Hermes' native plugin
registry rather than copying them into the user's shared skill catalog.

After reviewing the two job definitions, create the isolated nightly and
event-triggered review sessions explicitly:

```bash
hermes esra install-cron --schedule "0 2 * * *"
hermes esra status
```

The jobs use fresh sessions and only the `esra` and `skills` toolsets. A cheap
pre-check suppresses the 15-minute event job when the durable controller queue
has no pending review. This command is deliberately operator-run because cron
configuration is a protected host surface.
