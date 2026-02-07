# Scheduler

Agentic Console includes an in-process task queue and supports external scheduling.

## Internal queue

The TaskQueue executes work items sequentially and is used by the runtime loop.

## External scheduling

For cron-style runs, use your OS scheduler to invoke the CLI:

```
python runtime\run.py run "weekly report" --two-agent
```

## Suggested patterns

- Keep scheduled tasks short and deterministic.
- Use run artifacts to track outcomes.
- Use approvals for any risky or destructive steps.
