# ESRA Agents

Portable ESRA 1.2 skills and a shared local runtime for ChatGPT/Codex, Claude
Code, and Hermes Agent.

This repository is the canonical implementation source for five selective ESRA
skills, evidence records, bounded experiments, audits, portable export, and thin
host adapters. The runtime-neutral specification remains at
https://github.com/rrpauls/esra.

## Design

- One open Agent Skills tree for every supported host.
- One dependency-free runtime and portable exporter.
- Host-specific manifests, lifecycle event mappings, paths, and installers live
  only under `adapters/` and generated distributions.
- Routine work bypasses ESRA; focused skills work independently; a major change
  may receive at most one bounded review.

See [Architecture](docs/ARCHITECTURE.md), [runtime commands](docs/RUNTIME.md),
and [installation](INSTALL.md).

## Operational boundaries

ESRA Agents does not modify model weights, run as an autonomous background
service, start improvement cycles from hooks, promote skill changes, or mutate
host configuration automatically. Hooks record only allowlisted lifecycle
metadata and discard prompt, transcript, tool input/output, secret, and raw
session content.

Package validation is not native-host validation. Capability claims remain
gated by the host pilot defined in `rrpauls/esra`.

## Development

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 scripts/build_distributions.py
python3 scripts/validate_distributions.py
```

Licensed under Apache-2.0. See `NOTICE` for provenance and trademark separation.
