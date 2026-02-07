# Upgrade

## Before you upgrade

- Back up `data/memory.db` and `data/runs/`.
- Save `.env` if you store config there.

## Upgrade steps

1. Pull the latest code.
2. Reinstall dependencies if needed.
3. Run `scripts\run_smoke.ps1`.

## After upgrade

- Verify the UI loads.
- Check `data/agentic.log` for errors.
- Confirm recent runs are visible in `data/runs/`.
