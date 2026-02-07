# Tools

## Registry

Tools are registered in `tools/` and exposed through the tool registry. The registry provides tool metadata, risk level, and approval requirements.

## Risk and approvals

- `safe` tools typically run without confirmation.
- Higher-risk tools can require step approval.

## Allowlists

- Shell commands: `AGENTIC_ALLOWED_SHELL`
- MCP providers: `AGENTIC_ALLOWED_MCP`
- Package installs: `AGENTIC_ALLOWED_PIP`

## Inspect available tools

```
python runtime\run.py agent tools
```
