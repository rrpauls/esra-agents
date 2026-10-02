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
RELEASE_TAG=v0.4.0
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
