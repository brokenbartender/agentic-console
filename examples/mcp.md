# MCP Examples

## Configure endpoints

```
set MCP_ENDPOINTS=local=http://127.0.0.1:9000/mcp
```

## Allow providers

```
set AGENTIC_ALLOWED_MCP=local,github
```

## Python usage

```python
from mcp_adapter import MCPAdapter

adapter = MCPAdapter()
print(adapter.list_providers())
print(adapter.list_tools("github"))
```
