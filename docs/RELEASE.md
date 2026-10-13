# Release and stable promotion

VERSION is canonical. Bump it for each publishable change and run
`.venv/bin/python scripts/sync_manifests.py`. Commit the synchronized manifests
and matrices after review. Antigravity disallows native version metadata, so its
build writes separate distribution.json. Immutable ZIPs remain checksummed.

Tag that exact validated commit `v<VERSION>`. Release CI checks tag/version
agreement, manifests, skills, unit tests, all distributions, checksum coverage and
available host validators before uploading the complete nine-archive set.
It checks out the tag and never overwrites previously attached assets. Do not
rerun a new builder against an old tag or attach current builds to an old release.

Stable promotion is deliberately operator-controlled because branch protection
and release acceptance are external policy. After reviewing the tag's successful
release job and all attached SHA256SUMS, run from a clean release checkout:

```bash
git fetch origin --tags
RELEASE_TAG="v$(cat VERSION)"
RELEASE_SHA=$(git rev-parse "$RELEASE_TAG^{commit}")
git push origin "$RELEASE_SHA:refs/heads/stable"
```

This is a normal fast-forward push, with no force option. If protection requires
a PR, open a reviewed release PR targeting stable; do not bypass protections.
The first stable branch may be created only at an accepted validated release.
Do not promote a prerelease while the autonomous host/soak gates remain open.
Current host documentation must be rechecked before merge and stable promotion.

No external marketplace, catalog, npm registry or API environment is published
by these workflows. OpenAI public submission uses the hooks-free web artifact;
Claude organization sync requires an organization-owned private/internal mirror.
Hermes and Antigravity catalogs need separate admission/publication. Registry
credentials and organization automation do not belong in this repository.

## Catalog availability and first stable publication

Main's checked-in Codex and Claude catalogs are explicitly `esra-agents-edge`
with plugin ref `main`. Normal synchronization restores that exact contract.
Stable catalogs are staged separately with `--stage-marketplace ... --channel stable`;
a catalog checkout ref never overrides its plugin ref. Do not create stable on
an unaccepted release candidate to repair installation.

First stable sequence: validate the candidate and host/soak gates; accept its
exact tagged release and assets; authorize protected promotion; publish stable;
then run `scripts/verify_published_sources.py --catalog-root <staged-stable>` and
native installs against the published staged catalog/mirror in disposable profiles.
Only after those pass announce stable availability. There is no requirement for
stable to exist before its first authorized promotion. Package/release CI remains
offline with respect to source readiness; it never promotes stable automatically.

For main, run the separate published-source workflow after publication and
`scripts/verify_installations.py --host codex --install --source https://github.com/rrpauls/esra-agents/`.
The source probe checks currently advertised refs, not whether unpushed changes
are published. Native source smoke reads the actual remote catalog and can fail
while local packages and loopback fixture tests pass. Live hooks and skill use
remain separate host gates.
