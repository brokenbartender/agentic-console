# Observability

## Logs

- App logs: `data/agentic.log`
- Run artifacts: `data/runs/<run_id>/`

## Events

The memory store records events, audit logs, and debug logs in `data/memory.db`.

## Telemetry integrations

Optional telemetry modules include AgentOps, Langfuse, and OpenTelemetry. Configure them via env vars in `docs/telemetry.md`.

## Tips

- Use run artifacts for postmortems.
- Keep `data/` under versioned backups for long-running deployments.
