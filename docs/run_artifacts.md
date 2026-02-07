# Run Artifacts

Each run writes artifacts under `data/runs/<run_id>/`.

## Files

- `plan.json`: plan schema and step definitions
- `report.json`: execution report
- `summary.md`: human-readable summary
- `state.json`: last known status

## Uses

- Debug failed runs
- Audit tool usage and risk
- Reconstruct what happened without rerunning tools
