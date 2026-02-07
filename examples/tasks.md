# Tasks Examples

## Simple headless run

```
python runtime\run.py run "summarize key risks" --two-agent
```

## Use memory before running

```
python runtime\run.py memory search "risk"
python runtime\run.py run "use the memory above to draft a summary" --two-agent
```

## Plan schema skeleton

```json
{
  "run_id": "run-123",
  "trace_id": "trace-123",
  "goal": "Ship weekly status",
  "success_criteria": ["summary produced", "saved to file"],
  "steps": [
    {
      "step_id": 1,
      "title": "Gather changes",
      "intent": "Collect updates from logs",
      "tool": "shell",
      "args": {"cmd": "git log -5 --oneline"},
      "risk": "safe"
    }
  ]
}
```
