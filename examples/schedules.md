# Schedules Examples

## Windows Task Scheduler (conceptual)

```
schtasks /Create /SC DAILY /TN "Agentic Daily" /TR "python runtime\\run.py run \"daily brief\" --two-agent" /ST 09:00
```

## Manual scheduled run

```
python runtime\run.py run "nightly metrics" --two-agent
```
