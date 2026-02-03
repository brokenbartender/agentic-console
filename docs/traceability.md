# Traceability

- All instructions, plans, tools, and responses are logged in `data/agentic.log`.
- Use `/api/metrics` for lightweight runtime diagnostics.
- Add additional trace views as needed (UI panel or JSON export).
- Logs can be redacted with `AGENTIC_REDACT_LOGS` and scoped with `AGENTIC_PURPOSE`.
- Event retention is controlled via `AGENTIC_EVENT_RETENTION_SECONDS`.
- RAG chunks now store provenance (source path + offsets) and source ranking for explainability.
