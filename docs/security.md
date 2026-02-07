# Security

## Trust boundaries

- UI and CLI operate locally. Treat the host as the trust boundary.
- A2A and MCP introduce network surfaces. Use shared secrets and allowlists.

## Allowlists

- Shell allowlist: `AGENTIC_ALLOWED_SHELL`
- MCP allowlist: `AGENTIC_ALLOWED_MCP`
- Path/domain allowlists: `AGENTIC_ALLOWED_PATHS`, `AGENTIC_ALLOWED_DOMAINS`

## Secrets

- Store API keys in environment variables or `.env`.
- Avoid pasting secrets into prompts or memory.

## Data at rest

- Logs: `data/agentic.log`
- Memory DB: `data/memory.db`
- Run artifacts: `data/runs/<run_id>/`

## Recommended practices

- Enable approvals for high-risk tools.
- Use separate OS users or machines for sensitive tasks.
- Rotate tokens used for MCP and telemetry.
