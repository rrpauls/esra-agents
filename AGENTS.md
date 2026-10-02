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

## Host packaging and installation

Canonical host-neutral skills live in skills/. Host manifests and hooks remain
at native discovery paths. Claude uses .claude-plugin/ and hooks/hooks.json;
OpenAI uses adapters/openai/hooks.json. Hermes root plugin.yaml is synchronized
from adapters/hermes/plugin/plugin.yaml and __init__.py delegates to its adapter.
Antigravity hooks.json is canonical, but its closed native manifest is generated:
the generic repository-root plugin.json is not a native Antigravity plugin.

Use distributions/targets.json and INSTALL.md to select the exact host surface.
Prefer host-managed Git/marketplace installations where supported. Stable follows
stable, edge follows main, immutable follows a tag/full SHA. Local ZIPs are manual
replacement. Never assume a catalog ref overrides a plugin source ref. Stage
alternate catalogs with scripts/sync_manifests.py --stage-marketplace.

Web-only packages deploy portable workflows without ESRA local runtime/hooks.
Claude Web and Gemini require different individual skill ZIP layouts. Grok Build
reuses Claude compatibility; Grok Web/Bot is a separate limited surface. No
background ESRA updater or unrequested auto_apply setting is permitted.

VERSION is the only release version source. Run scripts/sync_manifests.py after a
bump; CI checks manifest and generated-matrix agreement. Antigravity metadata is
separate from its native closed manifest. Native validators, package tests and
actual runtime behavior are separate evidence levels. Do not modify user profiles
for testing; use scripts/verify_installations.py and disposable profiles.

## Release requirements

Every GitHub release, including prereleases, must include validated builds for
every host supported by that tag and `SHA256SUMS`. Run the tagged
`scripts/build_distributions.py` and `scripts/validate_distributions.py`; attach
all generated ZIPs and the checksum file, including `esra-agents-skills.zip`
with individual skill ZIPs, Markdown files, and inner checksums. Keep the OpenAI
marketplace, direct plugin and web-safe artifacts separate, and include dedicated
Claude Web skill packaging. Follow docs/RELEASE.md for controlled stable promotion. Never attach builds from another
revision to an older release. When adding a host, update the builder and
validator so future releases include it automatically.

## Verification commands

Run from the repository root using its virtual environment. Create it with
`python3 -m venv .venv` only if no project environment exists:

```bash
.venv/bin/python scripts/sync_manifests.py --check
.venv/bin/python scripts/validate_skills.py
.venv/bin/python scripts/validate_plugin.py
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/build_distributions.py
.venv/bin/python scripts/validate_distributions.py
.venv/bin/python scripts/verify_installations.py
```
