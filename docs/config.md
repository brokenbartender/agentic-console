# Config

Configuration is loaded from environment variables. By default `.env` in the repo root is read.

## Env file

- Default: `.env`
- Override: `AGENTIC_ENV_FILE`

## Common settings

- `AGENTIC_DATA_DIR`: base data directory
- `AGENTIC_MEMORY_DB`: memory database path
- `AGENTIC_LOG_FILE`: log file path
- `AGENTIC_WEB_HOST`: UI host
- `AGENTIC_WEB_PORT`: UI port
- `AGENTIC_AUTONOMY_LEVEL`: supervised|semi|autonomous
- `AGENTIC_ALLOWED_PATHS`: filesystem allowlist
- `AGENTIC_ALLOWED_DOMAINS`: network allowlist
- `AGENTIC_ALLOWED_SHELL`: shell allowlist
- `AGENTIC_ALLOWED_MCP`: MCP allowlist
- `AGENTIC_A2A_*`: A2A network settings
- `OPENAI_MODEL` and `OLLAMA_MODEL`: model selection

## Cost settings

- `OPENAI_COST_INPUT_PER_1M`, `OPENAI_COST_OUTPUT_PER_1M`
- `OLLAMA_COST_INPUT_PER_1M`, `OLLAMA_COST_OUTPUT_PER_1M`
