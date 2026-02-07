# Telemetry

Optional telemetry integrations emit structured events.

## AgentOps

- Enable by setting `AGENTOPS_API_KEY`.

## Langfuse

- Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.
- Optional: `LANGFUSE_HOST`.

## OpenTelemetry

- Set `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Optional: `OTEL_SERVICE_NAME`.

## Notes

Telemetry is best-effort. Failures are ignored to keep the runtime stable.
