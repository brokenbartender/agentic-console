# CLI

The runtime CLI lives in `runtime/run.py`.

## Commands

Run a task:

```
python runtime\run.py run "draft a summary" --two-agent
```

Agent introspection:

```
python runtime\run.py agent describe
python runtime\run.py agent status
python runtime\run.py agent tools
```

Memory utilities:

```
python runtime\run.py memory show
python runtime\run.py memory search "topic"
python runtime\run.py memory pin "important detail"
python runtime\run.py memory clear
```

Workflow utilities:

```
python runtime\run.py workflow list
python runtime\run.py workflow run workflows\example.json --goal "ship report"
python runtime\run.py workflow create "new_workflow"
```
