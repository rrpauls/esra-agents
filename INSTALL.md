# Installation by host surface

`distributions/targets.json` defines package and capability contracts. The matrix
below is generated; `scripts/sync_manifests.py --check` rejects documentation drift.
Official sources, checked on 2026-10-02, are recorded per target. Package validation
is distinct from host loading, actual hook execution and production readiness.

## Channels, archives and verification

- **Stable:** moving `stable` branch, promoted after a validated tagged release.
- **Edge:** `main`; development changes can require a new plugin version before
  a host version-based updater refreshes its cached copy.
- **Immutable:** version tag or full commit SHA; no automatic movement. Hermes
  accepts only a full 40-character commit SHA for `--ref`.

Version 0.4.0 is a release candidate in this checkout. The stable branch and
v0.4.0 tag must be published by the release operator before these remote examples
are usable. See [Release procedure](docs/RELEASE.md). Existing v0.3.0 assets stay
immutable. No ESRA background updater is installed.

Download ZIPs and `SHA256SUMS` from the same tagged release, then verify:

```bash
shasum -a 256 -c SHA256SUMS
```

Extract the outer `esra-agents-skills.zip` or `esra-agents-claude-skills.zip`
bundle and verify its inner checksums before uploading individual `zip/*.zip`.
Each contains all five canonical skills and matching raw `markdown/*.md` files.
All local script hooks require Python 3.10+ in the host execution environment.
The dependency-free hook entry point imports sibling runtime files directly;
it does not depend on globally installed project packages.

## Codex and ChatGPT Desktop/local marketplaces

The stable repository marketplace follows the stable **plugin** source:

```bash
codex plugin marketplace add rrpauls/esra-agents --ref stable
codex plugin add esra-agents@esra-agents
codex plugin list --json
codex plugin marketplace upgrade esra-agents
codex plugin remove esra-agents@esra-agents
codex plugin marketplace remove esra-agents
```

For a release/offline installation, extract `esra-agents-openai.zip`, add its
`esra-agents-openai/` directory with `codex plugin marketplace add /absolute/path/to/esra-agents-openai`,
then use the same add/list/remove commands. Updates to extracted copies require
manual replacement and native removal/re-addition of the local marketplace and
plugin; `marketplace upgrade` supports Git sources, not local catalogs.
Old releases whose extracted
folder is `esra-agents-marketplace/` still use that directory.

ChatGPT Desktop exposes local sources in its Plugins Directory. Restart after
replacing a local plugin. Codex's native `marketplace upgrade` refreshes managed
sources; ESRA does not promise unattended local updates. Hook installation does
not grant trust: review scripts and approve non-managed hooks in the host.
Hooks record only allowlisted lifecycle metadata and never steer execution.

Adding a catalog from `main` does **not** override a plugin entry that says
`stable`. Stage explicit alternative catalogs from this checkout instead:

```bash
.venv/bin/python scripts/sync_manifests.py --stage-marketplace /tmp/esra-edge --channel edge
codex plugin marketplace add /tmp/esra-edge
codex plugin add esra-agents@esra-agents-edge
.venv/bin/python scripts/sync_manifests.py --stage-marketplace /tmp/esra-pinned --channel immutable --ref v0.4.0
codex plugin marketplace add /tmp/esra-pinned
codex plugin add esra-agents@esra-agents-immutable
```

An exact commit can replace `v0.4.0`. Pinned entries stay fixed even when their
catalog is refreshed. Staged catalogs are local files; their plugin sources are
native tracked Git sources. Repository installations do not require repacking.

## ChatGPT GitHub-managed workspace marketplace

An administrator imports `rrpauls/esra-agents` at `stable` from Workspace
settings → Plugins → Marketplaces. Public and private repositories are supported
subject to the workspace's GitHub access. OpenAI owns daily synchronization;
**Sync now** requests a refresh. Select the enabled installation policy for
members. Removing the marketplace or changing the policy is an admin operation.
For edge/pinned provisioning, commit the staged catalog from above into a
separate admin-controlled repository. Never advertise an immutable source as
updateable. A synced plugin does not deploy Python into ChatGPT Web.

[Official workspace guidance](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt).

## Direct OpenAI plugin, ChatGPT Work and Agents API

`esra-agents-openai-plugin.zip` contains one plugin root with portable and Codex
manifests, five skills, hook resources and runtime. It is a direct plugin archive,
separate from the backward-compatible marketplace wrapper. Upload where the host
accepts a plugin archive; use the marketplace wrapper for local catalog installs.
Full local/Work execution provides skills plus runtime/hooks only where scripts
are present, executable and trusted. A Work label alone does not prove execution.

Agents API supports one ZIP per plugin in `environment.plugins` for hosted
sandboxes, and staged plugin directories in self-hosted environments. Follow
[the API environment contract](https://developers.openai.com/api/docs/guides/agents-api/tools/plugins).
Keep environment permissions unchanged. Replace a ZIP or directory to update;
remove its environment plugin configuration to uninstall. Credential-backed
provisioning/invocation must be tested separately in an authorized disposable
environment; ordinary CI does not make API calls or create billable sandboxes.

## ChatGPT Web / public directory

Use `esra-agents-openai-web.zip` for manual import/submission where available.
It has one plugin root, canonical skills and presentation metadata, with no
hook declarations, hook scripts, local runtime or controller. Public submission
requires review; ESRA is not claimed to be listed. Skills/metadata updates require
a replacement ZIP. Remove through the plugin's host controls.

[OpenAI submission rules](https://developers.openai.com/plugins/deploy/submission)
currently reject lifecycle-hook packages. Web-only installation provides portable
reasoning workflows; optional runtime references inside unchanged canonical skills
apply only if separately provisioned and authorized.

## Claude Code

```bash
claude plugin marketplace add rrpauls/esra-agents#stable
claude plugin install esra-agents@esra-agents
claude plugin update esra-agents@esra-agents
claude plugin marketplace update esra-agents
claude plugin uninstall esra-agents@esra-agents
claude plugin marketplace remove esra-agents
```

Native custom-marketplace auto-update is off by default. In `/plugin` →
Marketplaces, select this marketplace and **Enable auto-update**. Administrators
can set `autoUpdate: true` for its managed `extraKnownMarketplaces` entry. ESRA
never changes that setting. Each published plugin change bumps VERSION.

For edge/pinned installs, use the staged catalogs above with `claude plugin
marketplace add /tmp/esra-edge` (or `/tmp/esra-pinned`) and the matching qualified
plugin name. Both the catalog ref and the plugin source must select the channel.
For local development or an extracted `esra-agents-claude.zip`:

```bash
claude plugin validate --strict /absolute/path/to/esra-agents-claude
claude --plugin-dir /absolute/path/to/esra-agents-claude
```

Local directories/ZIPs update by replacing files; omit `--plugin-dir` to unload
an ephemeral local plugin. Native hooks live at `hooks/hooks.json`, resolve
`${CLAUDE_PLUGIN_ROOT}` and use the host's data directory. Review hook commands
and host trust prompts before enabling them.
[Official update policy](https://code.claude.com/docs/en/plugins/host-marketplace).

## Claude Web personal skills

Extract `esra-agents-claude-skills.zip`; upload individual `zip/<skill>.zip`
through Customize → Skills. Each ZIP contains `<skill>/SKILL.md`, license and
notice **inside** that folder. Gemini's root-file ZIP is a different format.
Enable cloud code execution/Skills where the account requires them, then test a
matching prompt. This package deploys no ESRA Python runtime, local lifecycle
hooks, filesystem persistence or autonomous controller. Replace/upload each skill
manually; delete it from Skills to uninstall.
[Official ZIP structure](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills).

## Claude Team / Enterprise organization provisioning

Provision individual skills through organization Plugins & skills settings, or
connect a private/internal GitHub marketplace with the Claude GitHub App installed.
The public canonical repository cannot itself be the synchronized organization
marketplace. Use **public canonical source → private/internal organization mirror
→ Claude marketplace sync**. Mirror the validated revision and catalog without
putting credentials or proprietary automation here. An admin enables automatic
sync; manual **Update** remains available. Removing the plugin from the mirror
and syncing removes it. Hook/runtime availability depends on the execution
surface; organization provisioning does not deploy local Python to web chats.
[Official organization restrictions](https://support.claude.com/en/articles/13837433-manage-plugins-for-your-organization).

## Gemini Web skills

Extract `esra-agents-skills.zip`. Settings → Skills → Upload accepts each
`zip/<skill>.zip`, raw `SKILL.md` or extracted skill folder. Gemini ZIPs place
`SKILL.md` at ZIP root. Review and create the skill; eligibility depends on the
account. Updates are manual replacement; remove the skill in Settings. These
skills provide no ESRA hooks, runtime, autonomous persistence or controller.
[Google's upload requirements](https://support.google.com/gemini/answer/17094296?hl=en).

## Grok Build / CLI

Reuse the Claude plugin archive and root marketplace; no duplicated Grok source
tree is needed. Grok sets both its native root/data variables and Claude aliases.
The shared hook detects `GROK_PLUGIN_ROOT` and records under `GROK_PLUGIN_DATA`.

```bash
grok plugin marketplace add rrpauls/esra-agents
grok plugin install rrpauls/esra-agents@stable --trust
grok plugin details esra-agents
grok inspect --json
grok plugin update esra-agents
grok plugin marketplace update esra-agents
grok plugin uninstall esra-agents --confirm
```

Use `@main` for edge, `@v0.4.0` or `@<full-commit-sha>` for immutable direct
installs. A catalog install follows its entry's source; use a staged edge/pinned
catalog for that path. A local path or `grok --plugin-dir /absolute/path` supports
development; `.grok/plugins/` and `~/.grok/plugins/` support discovery. Review
code before granting `--trust`; project hooks need host trust. Native manual
updates are supported; unattended updates are not claimed.
[xAI compatibility and discovery](https://docs.x.ai/build/features/skills-plugins-marketplaces).

## Grok Web / Bot

Use individual `markdown/*.md` files from `esra-agents-skills.zip` as reusable
instructions where the account supports file-based skills. Bot surfaces without
that feature can consume the instructions in context only; persistent Bot skill
registration is unverified. ZIP import is unverified. Replace the instructions
manually and remove them in the host's library or bot configuration. No ESRA
local hooks, runtime, filesystem persistence or autonomous controller is deployed.

## Hermes Agent / Desktop

The repository root now exposes native `plugin.yaml` and a small Python entry
point delegating to the existing adapter. Managed installation registers all five
skills, four hooks and the guarded controller. Explicit enablement is required.

```bash
# Native install follows the repository default branch (main / edge).
hermes plugins install rrpauls/esra-agents --no-enable
hermes plugins enable esra-agents
hermes plugins check-updates
hermes plugins update esra-agents
hermes plugins remove esra-agents
```

Current Hermes `--ref` accepts **only exact commits**, not branch names. For
stable, clone its branch into the plugin directory and adopt that native source:

```bash
git clone --branch stable https://github.com/rrpauls/esra-agents.git ~/.hermes/plugins/esra-agents
hermes plugins adopt esra-agents
hermes plugins enable esra-agents
# Immutable installation (replace the placeholder with a verified full SHA):
hermes plugins install rrpauls/esra-agents --ref <40-character-commit-sha> --no-enable
```

Use separate profiles/directories rather than overwriting an existing install.
Branch-adopted update behavior must be verified on the installed Hermes version;
its update checker may compare remote HEAD even when Git pull follows stable.
Pinned sources remain pinned; deliberately install a new exact SHA to move them.

Hermes checks tracked sources periodically (`plugins.auto_update_check_hours`,
default 24). Applying updates requires `hermes plugins update` unless the operator
explicitly sets `plugins.auto_apply: true`; ESRA never enables it. Native metadata
belongs to Hermes. Dependencies and changed capabilities require host consent.

Desktop supports `hermes://plugin/install?repo=rrpauls/esra-agents`, with a
confirmation dialog and component selection; it follows the default branch.
Custom sources can require native scan confirmation. After reviewing caution
findings, use the host's explicit `--force` option; dangerous findings are still
blocked. Never disable scanning to install ESRA. No ESRA catalog listing is claimed. For offline use, extract the Hermes ZIP and
review/run `./install.sh`; it refuses overwrites and is **unmanaged**, updated
by manual replacement. Remove it through Hermes' plugin manager. It preserves
existing runtime/state locations and registers bundled skills instead of copying
them into the shared skill catalog.

After reviewing their definitions, `hermes esra install-cron --schedule "0 2 * * *"`
creates guarded review jobs explicitly. These review jobs are unrelated to plugin
updates and are never installed by package discovery.
[Official native install and update controls](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/).

## OpenClaw Gateway / CLI

```bash
openclaw plugins install --force --accept-capabilities git:github.com/rrpauls/esra-agents@stable
openclaw plugins enable --accept-capabilities esra-agents
openclaw plugins inspect esra-agents --runtime --json
openclaw plugins update esra-agents --dry-run
openclaw plugins update esra-agents
openclaw plugins uninstall esra-agents
```

Use `@main` for edge, a tag or exact SHA for reproducible source selection.
Do not invoke update on an immutable install; select a new reviewed ref explicitly.
Keep the native TypeScript adapter and package identity `@rrpauls/esra-agents`.
Release ZIP/local folders, `--link /absolute/path` development installs, packaged
`.tgz` and npm installs are native alternatives. Create a local tarball with
`npm pack --ignore-scripts`; a registry command such as `npm:@rrpauls/esra-agents`
becomes usable only after actual npm publication. ClawHub/catalog publication
has not been performed. Arbitrary ESRA Git sources use manual native updates;
trusted official-package auto-update policies do not make this source automatic.

`--force` acknowledges untrusted third-party code. The `agent_end` subscriber
requires explicit conversation-access consent:
`openclaw config set plugins.entries.esra-agents.hooks.allowConversationAccess true`.
Omit this consent to retain the other six sanitized hooks. ESRA discards message
payloads even when consent is granted. Restart/reload the Gateway as required and
inspect a real event separately; CLI registration alone is not live Gateway proof.
A separate `operator.admin` controller identity owns authorized Skill Workshop
promotion. Do not broaden the ordinary agent's scope.
[Official source/update commands](https://docs.openclaw.ai/cli/plugins).

## Google Antigravity CLI / IDE / 2.0

Extract `esra-agents-antigravity.zip` and install the **inner plugin directory**:

```bash
agy plugin install /absolute/path/to/esra-agents-antigravity
agy plugin list
agy plugin uninstall esra-agents
```

Manual IDE/2.0 installs place that folder in workspace `.agents/plugins/` or
`~/.gemini/config/plugins/`; CLI staging uses its own managed profile directory.
Do not unzip the enclosing folder inside another `esra-agents` folder. Custom
updates are manual replacement/reinstall. Build from a checkout of stable, main,
a tag or SHA to select the source channel for local development. Remove a manually
placed folder to uninstall; inspect `/hooks` and skill discovery after approval.

The native closed manifest accepts `name` and `description`; version is in
`distribution.json` and VERSION. The generic repository-root Agent Plugins
manifest is **not** a native Antigravity manifest. Use the generated package.
No curated Marketplace listing or automatic update is claimed. Hooks execute
only after host trust and Python provisioning. Relative command resolution and
actual hook execution still require an Antigravity integration run.
[Google's schema and installation paths](https://antigravity.google/docs/plugins).

## Generic Agent Skills consumers

Copy individual canonical `skills/<name>/` folders or use the portable bundle
according to the host's Agent Skills contract. Update/remove those folders with
the host's supported controls. These are portable reasoning workflows; lifecycle
hooks, runtime/controller and persistence are not guaranteed.

## Developer verification

From the repository root, create a project environment once (`python3 -m venv
.venv`), then use its interpreter:

```bash
.venv/bin/python scripts/sync_manifests.py --check
.venv/bin/python scripts/validate_skills.py
.venv/bin/python scripts/validate_plugin.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build_distributions.py
.venv/bin/python scripts/validate_distributions.py dist
.venv/bin/python scripts/verify_installations.py
.venv/bin/python scripts/verify_installations.py --host codex --install
```

For tracked source tests without publication, use `--host codex --install
--git-fixture` (also supported for Claude/Grok/Hermes). The fixture serves only a
disposable bare repository over loopback and never exposes host profiles. Hermes
requires a prepared `--hermes-cli`; `--trust-source` explicitly accepts caution
findings only for its isolated install. `--pin-fixture` verifies its exact-commit
update refusal. Opt-in unittest integrations use `ESRA_HOST_INTEGRATIONS=1` and,
for Hermes, `ESRA_HERMES_CLI` pointing at the prepared environment entry point.

The smoke harness reports PASS, SKIPPED or FAIL, uses disposable profiles and
never installs globally. `--install` permits isolated native installs; `--source`
with `--host` tests a published tracked Git source. Missing CLIs/credentials and
unavailable runtime bootstraps skip explicitly. A prepared Hermes environment
entry point can be supplied through `--hermes-cli`. API provisioning and live web
uploads remain separate credential/account tests. All hooks remain observational,
non-steering and privacy-allowlisted; no prompts, transcripts, tool payloads,
secrets or raw session identifiers are persisted.

<!-- distribution-matrix:start -->
<!-- Generated from distributions/targets.json; do not edit. -->
| Host / surface | Install modes (preferred first) | Stable / edge updates | Hooks | Runtime | Verification |
|---|---|---|---|---|---|
| OpenAI / Codex / Desktop | native-marketplace, git, release-zip, local-path | manual-native / manual-native | runtime-dependent | local | isolated native local and tracked Git marketplace/add/list/upgrade/remove; live hooks pending |
| OpenAI / ChatGPT GitHub workspace marketplace | native-marketplace, git | automatic / automatic | runtime-dependent | environment-dependent | official-docs; package-contract-tested; live-integration-pending |
| OpenAI / ChatGPT Work runtime | release-zip, local-path | manual-replace / manual-replace | runtime-dependent | environment-dependent | official-docs; package-contract-tested; live-integration-pending |
| OpenAI / ChatGPT Web / public directory | manual-upload, catalog-submission | manual-replace / manual-replace | none | none | official-docs; package-contract-tested; live-integration-pending |
| OpenAI / Agents API environments | manual-upload, local-path, release-zip | manual-replace / manual-replace | runtime-dependent | environment-dependent | official-docs; package-contract-tested; live-integration-pending |
| Claude / Claude Code | native-marketplace, git, local-path, release-zip | automatic-opt-in / automatic-opt-in | native | local | native strict manifests and isolated tracked Git install/list/update/remove; live hooks pending |
| Claude / Web personal skills | manual-upload | manual-replace / manual-replace | none | none | official-docs; package-contract-tested; live-integration-pending |
| Claude / Team / Enterprise marketplace | native-marketplace, manual-upload | automatic-opt-in / automatic-opt-in | runtime-dependent | environment-dependent | official-docs; package-contract-tested; live-integration-pending |
| Google / Gemini Web skills | manual-upload | manual-replace / manual-replace | none | none | official-docs; package-contract-tested; live-integration-pending |
| xAI / Grok Build / CLI | git, native-marketplace, local-path, release-zip | manual-native / manual-native | native | local | native validate and isolated tracked Git install/discovery/update/remove; five skills and hooks discovered; live dispatch pending |
| xAI / Grok Web / Bot instructions | manual-upload | manual-replace / manual-replace | none | none | file guidance only; persistent Bot skills and ZIP import unverified |
| Hermes / Agent / Desktop | git, local-path, release-zip, catalog-submission | manual-native / automatic-opt-in | native | local | native root/archive validation and registration; managed install/update/pin skipped: host package manager missing uv.lock |
| OpenClaw / Gateway / CLI | git, local-path, release-zip, tarball, npm, catalog-submission | manual-native / manual-native | native | local | official-docs; package-contract-tested; live-integration-pending |
| Google / Antigravity CLI / IDE / 2.0 custom | local-path, release-zip | manual-replace / manual-replace | native | local | official-docs; package-contract-tested; live-integration-pending |
| Agent Skills / Generic consumers | manual-upload, local-path, git | manual-replace / manual-replace | none | none | official-docs; package-contract-tested; live-integration-pending |
<!-- distribution-matrix:end -->
