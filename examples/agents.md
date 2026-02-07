# Agents Examples

## Inspect agent profile

```
python runtime\run.py agent describe
```

## Sample role definition (conceptual)

```json
{
  "role": "Planner",
  "goal": "Create a brief plan",
  "allowed_tools": ["plan", "analyze"]
}
```

## Two-agent loop

```
python runtime\run.py run "draft a release note" --two-agent
```
