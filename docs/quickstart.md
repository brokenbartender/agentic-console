# Quickstart

This quickstart gets a local Agentic Console session running with the NiceGUI dashboard and the headless CLI.

## Prereqs

- Python available on PATH
- `nicegui` installed for the dashboard

## Run the dashboard

1. Install the UI dependency:

```
pip install nicegui
```

2. Start the dashboard UI:

```
python dashboard.py
```

3. Open the UI in a browser:

```
http://127.0.0.1:8333
```

## Run headless from the CLI

Use the runtime CLI for scripted runs:

```
python runtime\run.py run "summarize this repo" --two-agent
```

## Where data lives

By default, run artifacts and logs live under `data/`. You can override with `AGENTIC_DATA_DIR`.
