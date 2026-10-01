# Portable skill distributions

Keep canonical instructions in `skills/`; generate a universal skills-only
download without host hooks, manifests, or runtime services. Gemini Web accepts
one skill per ZIP with `SKILL.md` at its root. Grok Web documents file-based
skill creation, but its ZIP import contract has not been verified.

Publish `esra-agents-skills.zip` alongside the five host plugin packages. Inside,
group individually importable ZIPs under `zip/` and unchanged skill instructions
under `markdown/`. Include installation instructions, license, notice, and
checksums for the inner files. Users extract the bundle before importing skills.
Rename the OpenAI asset and its extracted root to `esra-agents-openai`.

Validate deterministic output, root-level skill entrypoints, source equality,
complete checksum coverage, and rejection of missing or altered files. Package
validation does not establish native host behavior or successful web imports.
