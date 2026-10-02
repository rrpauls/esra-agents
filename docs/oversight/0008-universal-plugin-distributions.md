# Universal installation and lifecycle proposal

Date: 2026-10-02. Scope: packaging, native source tracking, validation and installation docs.

Keep the five canonical skills and private runtime unchanged. Introduce VERSION
and distributions/targets.json as the version and distribution contracts. Generate
host metadata and the installation/hook matrix from those contracts. Preserve the
OpenAI marketplace archive and add direct, web-safe and Claude Web skill packages.
Stage incompatible native manifests rather than overloading portable plugin.json.

Managed sources use stable (validated release), main (edge), or a tag/SHA
(immutable). Use host update commands and opt-in controls only; no ESRA updater.
Stable promotion is a reviewed, fast-forward release step after all checks and
uploads. Do not create or push the stable branch during implementation.

Hermes repository discovery will delegate to the existing native Python adapter,
preserving four hooks, five skills, plugin identity and explicit enablement.
Claude-compatible hooks will resolve Claude/Grok roots without storing payloads.
Web artifacts contain canonical skills and hooks-free presentation only.

Record official documentation sources and distinguish schema/package tests from
live integration. CLI checks use temporary profiles and skip unavailable tooling;
external catalogs and credential-backed API checks stay separate and opt-in.
Retain archive path, symlink, duplicate, corruption and checksum safeguards.

Existing uncommitted INSTALL.md, ARCHITECTURE.md and proposal 0007 belong to prior
work and must be preserved or incorporated without discarding their intent.

Native Hermes scanning interpreted regex rejection strings as executable commands.
Move the unchanged forbidden-text regex into runtime/review-policy.txt and add
regressions for its denials. Do not suppress the host scanner or relax guards.

The policy is plain JSON text, shared by Python and OpenClaw TypeScript. This
keeps rejection rules readable and eliminates executable regex command literals;
Hermes still reports the policy as caution, which requires native user consent.
