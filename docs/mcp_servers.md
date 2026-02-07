# MCP Servers

The MCP adapter can route to local providers or remote endpoints.

## Configure endpoints

- `MCP_ENDPOINTS` supports comma-separated `name=url` pairs.
- `MCP_GITHUB_URL` and `MCP_DRIVE_URL` provide built-in providers.

Example:

```
set MCP_ENDPOINTS=local=http://127.0.0.1:9000/mcp,docs=http://127.0.0.1:9100/mcp
```

## Auth tokens

- `GITHUB_TOKEN` for the GitHub provider
- `GOOGLE_DRIVE_TOKEN` for the Drive provider

## Allowlist

Set `AGENTIC_ALLOWED_MCP` to restrict allowed providers.
