# Repository guidance

`esra-agents` is the canonical cross-host implementation of the ESRA 1.2
specification. Keep portable behavior in the shared core and isolate client
differences in `adapters/` and `distributions/`.

## Working rules

- Routine work bypasses ESRA. Use one focused skill for a focused need.
- A major architecture or skill change may receive one bounded ESRA review after
  the primary work. Reviews, logs, and audits never trigger another review.
- Preserve narrow skill triggers and progressive disclosure. Do not add mandatory
  skill chains.
- Keep `skills/` host-neutral. Host names, paths, hook formats, and installation
  mechanics belong in adapters or distribution metadata.
- Keep the shared runtime dependency-free and explicit about authorization,
  reversibility, evidence, and uncertainty.
- Never record prompts, transcripts, tool input/output, secrets, or raw session
  identifiers. Lifecycle hooks are observational and non-steering.
- Do not claim background execution, model-weight updates, automatic skill
  promotion, or native host integration without current reproducible evidence.
- Structural changes require a short proposal in `docs/oversight/` before code
  changes.

## Root-level hook and manifest files

The repository is a multi-host monorepo. Antigravity and Claude Code require
hook and manifest files at specific root-relative paths; those root-level files
**are the canonical sources** — there are no adapter copies for these hosts.

| Host | Canonical file | How it's discovered |
|------|---------------|---------------------|
| Antigravity | `hooks.json` | Plugin root |
| Claude Code | `.claude-plugin/plugin.json`, `hooks/hooks.json` | Standard Claude plugin paths |
| OpenAI/Codex | `adapters/openai/hooks.json` | `plugin.json` `extensions.com.openai.hooks` reference |
| Hermes Agent | `adapters/hermes/` | `install.sh` copies into `$HERMES_HOME` |
| OpenClaw | `adapters/openclaw/` | Native TypeScript adapter |

Edit the file at the path shown — there is no second copy to keep in sync.
`scripts/validate_plugin.py` confirms each host file exists on every run.

## Installing from a repository link

When a user pastes a link to this repository
(`https://github.com/rrpauls/esra-agents`) into a chat, determine which host
environment you are running in and install accordingly:

| Environment | Preferred action |
|-------------|-----------------|
| **Antigravity** | Download `esra-agents-antigravity.zip` from the [latest release](https://github.com/rrpauls/esra-agents/releases/latest), extract into `~/.gemini/config/plugins/esra-agents/`. If downloading fails, `git clone` works too — hooks are at the repo root. |
| **Claude Code** | Download `esra-agents-claude.zip` from the latest release. If cloning, hooks are at `hooks/hooks.json` and the manifest at `.claude-plugin/plugin.json`. |
| **ChatGPT / Codex** | Download `esra-agents-openai.zip`. For git clone, `plugin.json` already references `./adapters/openai/hooks.json`. |
| **Hermes Agent** | Download `esra-agents-hermes.zip` and run `install.sh`. |
| **OpenClaw** | Download `esra-agents-openclaw.zip`. |
| **Gemini Web / Grok Web** | Download `esra-agents-skills.zip` for portable skill import. |

Always prefer the ZIP release build for a clean, validated installation.
Fall back to `git clone` only when release downloads are unavailable; hooks are
committed at the expected root-relative paths for every host that uses them.

## Release requirements

Every GitHub release, including prereleases, must include validated builds for
every host supported by that tag and `SHA256SUMS`. Run the tagged
`scripts/build_distributions.py` and `scripts/validate_distributions.py`; attach
all generated ZIPs and the checksum file, including `esra-agents-skills.zip`
with individual skill ZIPs, Markdown files, and inner checksums. The OpenAI
package is `esra-agents-openai.zip`. Never attach builds from another
revision to an older release. When adding a host, update the builder and
validator so future releases include it automatically.

## Verification commands

Run from the repository root:

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 scripts/build_distributions.py
python3 scripts/validate_distributions.py
```
