# Shared runtime

The dependency-free runtime provides explicit local commands for evidence
records, trigger recommendations, baselines, bounded command comparisons,
dashboards, audits, and oversight proposals. The five skills work without it;
use it only when durable local state is explicitly requested.

## State resolution

Pass `--host openai`, `--host claude`, or `--host hermes`. Resolution order is:

1. `--data-dir`;
2. `ESRA_DATA_DIR`;
3. host variable (`PLUGIN_DATA`, `CLAUDE_PLUGIN_DATA`, or `HERMES_HOME`);
4. host default (`~/.codex/esra`, `~/.claude/esra`, or `~/.hermes/esra/data`).

Directories are mode `0700` and state files are mode `0600` where supported.
Symlinked state paths are refused.

## Examples

```bash
python3 runtime/esra_runtime.py --host openai trigger \
  --complexity 8 --major-change --session local-review

python3 runtime/esra_runtime.py --host claude record \
  --task-id adapter-review --outcome success \
  --evidence "unit tests passed" --verification "distribution extracted"

python3 runtime/esra_runtime.py --host hermes dashboard
```

`trigger` returns a recommendation only. `record` stores a result supplied by
the caller. No command starts an ESRA reasoning cycle or promotes a change.

Experiments require a hypothesis, guardrail, rollback, alignment score, and
explicit `experiment run`. Output content is represented only by digests in the
experiment record.

## Autonomous controller

`runtime/esra_controller.py` is a separate guarded state machine. Its commands
are `ingest`, `tick`, `next-review`, `complete-review`, `propose`, `evaluate`, `issue-token`, `consume-token`,
`promote`, `rollback`, `status`, `audit`, `pause`, and `resume`.

```bash
python3 runtime/esra_controller.py --state-dir /private/path/esra status
python3 runtime/esra_controller.py --state-dir /private/path/esra tick \
  --agent local-agent --nightly
```

`evaluate` accepts host-produced deterministic, alignment, replay, and blind
judge evidence for the exact revision. It requires at least three replay rows,
at least two candidate wins, no critical regression, and no proposal rationale
visible to the judge. It records `inconclusive` for a tie or insufficient
evidence. The controller never treats its own confidence as evaluation.

Direct `promote` is for a private agent-owned skill root. Native adapters use a
host workflow: snapshot first, then Skill Workshop or `skill_manage`, then
record activation only if the live text tree hashes to the evaluated revision.
