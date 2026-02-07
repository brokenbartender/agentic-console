# Troubleshooting

## UI does not load

- Confirm the server is running: `python dashboard.py`.
- Check the configured host/port: `AGENTIC_WEB_HOST` and `AGENTIC_WEB_PORT`.

## No tools appear

- Run `python runtime\run.py agent tools` to list available tools.
- Check allowlists that might block tool execution.

## Memory search returns nothing

- Ensure memories are not expired.
- Set `min_confidence` lower if needed.
- Verify scope (`shared` vs `private`).

## A2A messages not received

- Confirm `AGENTIC_A2A_LISTEN=true`.
- Check `AGENTIC_A2A_SHARED_SECRET` matches across peers.

## MCP calls fail

- Verify `MCP_ENDPOINTS` or provider URLs.
- Check `AGENTIC_ALLOWED_MCP` and provider tokens.
