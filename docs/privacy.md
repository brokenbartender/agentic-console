# Privacy

## Redaction

If `AGENTIC_REDACT_LOGS=true`, logs attempt to redact sensitive patterns before writing.

## Memory hygiene

- Avoid storing secrets in memory content.
- Use `memory clear` for sensitive sessions.

## Data retention

Event and audit retention windows are configurable:

- `AGENTIC_EVENT_RETENTION_SECONDS`
- `AGENTIC_AUDIT_RETENTION_SECONDS`
- `AGENTIC_DEBUG_RETENTION_SECONDS`

## Local-first

Data is stored locally under `data/` by default.
