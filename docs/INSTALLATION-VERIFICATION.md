# Installation verification — 0.4.0 candidate

Evidence recorded on 2026-10-02 against this working tree. This document separates
package contracts, native CLI discovery, and execution in a live host. No release,
stable branch promotion, catalog submission, or organization provisioning was
performed. The moving `stable` source requires the controlled promotion in
[RELEASE.md](RELEASE.md) before these changes are available remotely.

| Surface | Evidence | Remaining gate |
|---|---|---|
| All nine release archives | Deterministic builds, canonical skill equality, archive safety, version consistency, inner/outer checksums, distinct web layouts | Tagged release and artifact publication |
| Codex | Isolated local marketplace install/list/remove; temporary Git marketplace add/install/list/upgrade/remove reports version 0.4.0 | Actual trusted session hook execution; Desktop/ChatGPT UI behavior |
| Claude Code | Native strict plugin/marketplace validators; isolated Git marketplace install/list/update/uninstall | Model-backed sessions and live hook dispatch; auto-update consent/UI |
| Grok Build | Native validation; isolated Git install/details/inspect/update/uninstall; discovery reports exactly five skills and hooks | Live lifecycle event dispatch; separate marketplace command integration |
| Hermes | Native repository-root and release-package validation; isolated registration matches declared tools/hooks; five skills and four lifecycle hooks checked by regression tests | Managed install, update and immutable update-refusal require a working host package-manager environment |
| OpenClaw | Compiled JavaScript loads, registers seven hook handlers, uses canonical version and shared denial policy; package contracts validated | OpenClaw CLI unavailable: native Git install/update/pin and live dispatch skipped |
| Antigravity | Generated closed native manifest accepts only name/description; skills/hooks/runtime package contracts validated | `agy` CLI unavailable: native install/discovery/path resolution and live dispatch skipped |
| ChatGPT workspace / Work / Agents API | Official surface distinctions and package contracts checked | Workspace administrator import/sync, runtime availability, authenticated API integration |
| ChatGPT public directory | Hooks/runtime-free package contract checked | Submission review and publication |
| Claude Web / organization, Gemini Web, Grok Web/Bot, generic skills | Canonical portable skill content; separate Claude containing-directory ZIP and Gemini root-SKILL.md ZIP contracts | Actual UI uploads, administrator/private mirror provisioning, persistence and sync behavior |

Hermes' prepared native entry point validates the plugin, including an isolated
capability probe. Its security scanner reports `caution` for the declarative
filesystem-formatting **rejection** policy; this warning is retained. Managed Git
installation fails inside the host package manager because its own `workspace/pm/uv.lock`
is absent. The harness reports that specific unavailable runtime as `SKIPPED`,
does not repair the real Hermes installation, and does not claim that managed
updates or pinned update refusal passed. Dangerous findings remain host-blocked.
ESRA does not enable `auto_apply` during installation.

The native Git tests use an exact temporary working-tree snapshot, a loopback Git
server, and disposable home/configuration directories. They verify recognized
tracking and native update commands at the same revision; they do not prove a
remote version bump, unattended update application, marketplace publication,
seven-day soak, or model-backed behavior. No prompts, credentials, transcripts,
or user plugin configuration are copied into these profiles.

## Reproduce

Run from the repository root using the project environment:

```bash
.venv/bin/python scripts/sync_manifests.py --check
.venv/bin/python scripts/validate_skills.py
.venv/bin/python scripts/validate_plugin.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build_distributions.py
.venv/bin/python scripts/validate_distributions.py dist
(cd dist && shasum -a 256 -c SHA256SUMS)
.venv/bin/python scripts/verify_installations.py
ESRA_HOST_INTEGRATIONS=1 .venv/bin/python -m unittest tests.test_native_installations.NativeInstallationTests.test_codex_tracked_git_marketplace tests.test_native_installations.NativeInstallationTests.test_claude_tracked_git_plugin tests.test_native_installations.NativeInstallationTests.test_grok_tracked_git_skills_and_hooks -v
```

Default smoke tests run package contracts and available cold validators only.
`--install` explicitly enables disposable native installations; `--git-fixture`
exercises source tracking without publishing the working tree. Prepared Hermes
environments can be selected with `--hermes-cli`; integration tests use
`ESRA_HERMES_CLI`. `--trust-source` is an explicit isolated Hermes caution-review
choice, not a default installation policy. `--pin-fixture` tests Hermes' exact-SHA
update refusal once its managed runtime is available. Missing CLIs and specified
unavailable host environments are skipped; other native command failures fail
the harness. See [INSTALL.md](../INSTALL.md) and `distributions/targets.json` for
per-surface official documentation and current capability declarations.
