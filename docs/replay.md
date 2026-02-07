# Replay

Replay mode helps you inspect past runs without re-executing tools.

## Enable replay

Set `AGENTIC_REPLAY_MODE=true` to load run state without executing side effects.

## Artifacts used for replay

Run artifacts are stored under `data/runs/<run_id>/`:

- `plan.json`
- `report.json`
- `summary.md`
- `state.json`

## When to use

- Review outputs after a crash
- Validate a plan before running it again
- Compare outputs across versions
