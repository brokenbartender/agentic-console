# Perf

## Planning limits

- `AGENTIC_MAX_PLAN_STEPS` controls plan size.
- `AGENTIC_MAX_TOOL_CALLS` limits tool execution.

## Memory and embeddings

- `AGENTIC_EMBEDDING_DIM` impacts memory search speed and size.
- `AGENTIC_MEMORY_PRUNE_INTERVAL_SECONDS` controls pruning cadence.

## UI responsiveness

- Keep logs under control to avoid large UI payloads.
- Use headless runs for long tasks.

## Practical tips

- Prefer smaller plans for tight feedback loops.
- Cache or pin frequent context into memory.
