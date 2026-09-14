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

## Verification

Run from the repository root:

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_plugin.py
python3 -m unittest discover -s tests -v
python3 scripts/build_distributions.py
python3 scripts/validate_distributions.py
```
