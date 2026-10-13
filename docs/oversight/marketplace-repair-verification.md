# Marketplace repair verification — 2026-10-13

## Change

Main's official Codex and Claude catalogs now identify `esra-agents-edge` and
advertise plugin source `main`. Normal synchronization restores this contract;
offline validators reject stable/name drift. Stable and immutable staging remain
explicit, with stable promotion and release gates unchanged. The follow-up delivery bumps VERSION to 0.4.1 and synchronizes manifests.
Release publication and stable promotion remain separate.

Changed implementation: `.agents/plugins/marketplace.json`,
`.claude-plugin/marketplace.json`, `scripts/sync_manifests.py`,
`scripts/validate_plugin.py`, `scripts/verify_installations.py`,
`scripts/verify_published_sources.py`. Regression coverage:
`tests/test_installation_contract.py`, `tests/test_native_installations.py`,
`tests/test_published_sources.py`. Documentation: `INSTALL.md`, `docs/RELEASE.md`,
`docs/oversight/marketplace-source-readiness.md` and this report. The independent
manual `.github/workflows/published-sources.yml` probes advertised public refs;
package/release CI does not depend on first stable publication.

The version bump also updates VERSION, plugin.json, .codex-plugin/plugin.json,
.claude-plugin/plugin.json, package.json, openclaw.plugin.json,
esra-conformance.json, plugin.yaml and adapters/hermes/plugin/plugin.yaml.

## Evidence

- `sync_manifests.py --check`, `validate_skills.py`, `validate_plugin.py`: pass.
- Unit discovery: 79 tests, pass; 8 opt-in native tests skipped normally.
- Explicit Codex native tests: 2 pass in disposable profiles. Positive loopback
  Git fixture: marketplace add, plugin add/list (version, installed=true and
  enabled=true asserted), upgrade, remove. Negative fixture:
  catalog add succeeds, plugin add fails specifically on absent stable.
- All nine distributions built and validated with checksum coverage.
- `verify_installations.py`: package contracts pass; Claude strict plugin/catalog
  validators and Grok validator pass. Codex/Antigravity cold validators unavailable;
  Hermes managed launcher skipped; OpenClaw CLI unavailable. These are explicit
  host coverage gaps, not proof of native runtime execution.
- Python compilation and `git diff --check`: pass.
- Online source probe against local repaired catalogs: advertised main resolves.
- Public main resolves to `4ea4cbb4ff31e166113d926c17996586c9e92b52`.
  That full SHA was fetched and checked out successfully in isolation.
  `stable` and `v0.4.0` return no matching remote refs (`--exit-code` used).
- Actual public native source smoke: catalog `esra-agents` adds successfully;
  installing `esra-agents@esra-agents` still fails with `git checkout stable` /
  missing pathspec. Downloaded catalog identity is discovered from the temporary
  profile, so this result does not confuse old and repaired catalog names.

## Initial repair boundaries (before delivery)

At the initial local verification, repair and disposable native fixture validation
were complete. Public Git
still served the old broken catalog; publication was outside the initial task.
After an authorized publication, run the official-URL native smoke again before
announcing installability. The online ref probe alone cannot prove that the
public catalog includes unpushed changes. Live hooks, UI actions, skill use in a
new chat and other hosts' native installs were not tested by this repair.

User profiles and the working immutable installation were not modified. Docker
configuration was absent, so no container runtime was required. Initial worktree
was clean. No push, merge, release publication or stable promotion was performed.
