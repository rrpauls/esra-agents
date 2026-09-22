# Oversight proposal 0003: fail-closed completion and artifact evidence

## Decision

Treat missing or ambiguous command completion as inconclusive and allow a
bounded experiment to require concrete output artifacts per variant. A command
that exits zero is not successful when a declared artifact is missing, empty,
unchanged from before that invocation, or has an invalid image envelope.

## Bounds

- Artifact checks are local, read-only, and explicitly configured.
- The runtime stores paths and verification status, never artifact contents.
- Image checks remain dependency-free and validate the supported container
  envelope; host adapters may add stronger decoders without weakening this gate.
- Natural-language guardrail text is never evaluated as code. Optional explicit
  verifier commands provide the executable predicate without a shell.

## Verification

- Regression tests cover missing, empty, stale, and valid generated artifacts.
- Existing experiments without artifact declarations retain exit-code checks.
- Full runtime and distribution validation must remain green.

## Rollback

Remove the optional artifact declarations. Existing experiment records remain
readable because absent declarations default to an empty list.
