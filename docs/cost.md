# Cost

Cost reporting is tracked in the execution report and depends on configured per-token rates.

## Configure rates

Set per-million token rates for each backend:

- `OPENAI_COST_INPUT_PER_1M`
- `OPENAI_COST_OUTPUT_PER_1M`
- `OLLAMA_COST_INPUT_PER_1M`
- `OLLAMA_COST_OUTPUT_PER_1M`

## Reporting

Execution reports include a `cost` field that aggregates the run cost where available.

## Tips

- Keep plans short to reduce tool calls.
- Use cached memory to avoid repeated analysis.
