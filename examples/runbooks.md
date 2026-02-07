# Runbooks Examples

## Investigate a failed run

1. Open `data/runs/<run_id>/summary.md`.
2. Inspect `report.json` for the failure reason.
3. Review `data/agentic.log` for errors.

## Validate a policy change

1. Set the new env variables.
2. Run `scripts\run_smoke.ps1`.
3. Review logs for blocked actions.
