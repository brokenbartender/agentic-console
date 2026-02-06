# Agentic Console

Agentic Console is a local agent operating system: one chat UI, two-agent plan/execute loop, and a clear safety model.

## 60-second quickstart

1. Install requirements:

```
pip install nicegui
```

2. Start the app:

```
python C:\Users\codym\AgenticConsole\app.py
```

3. Open the UI:

```
http://127.0.0.1:8333
```

## What problem this solves

- Run complex tasks through a single chat interface.
- The planner creates a structured plan; the executor runs it.
- Approvals are required for risky actions.

## Canonical runtime

Everything runs through `runtime/run.py` and the lifecycle loop in `runtime/lifecycle.py`.

Examples:

```
python C:\Users\codym\AgenticConsole\runtime\run.py run "analyze this repo and summarize risks" --two-agent
python C:\Users\codym\AgenticConsole\runtime\run.py agent tools
python C:\Users\codym\AgenticConsole\runtime\run.py memory show
python C:\Users\codym\AgenticConsole\runtime\run.py workflow list
```

## Safety & trust model

- Tools are tagged by risk level.
- Destructive actions require explicit approval.
- Autonomy level can be tuned in config.

## Extending the system

- Add tools: `tools/registry.py`
- Add agents: `agents.py`
- Add workflows: `workflows/`

## UI

- Default UI: NiceGUI dashboard (`dashboard.py`)
- Legacy UI: set `AGENTIC_UI=tk`

## A2A handshake

Automatic peer handshakes are **off** by default. To enable:

```
set AGENTIC_A2A_HANDSHAKE=true
```

### Headless + NiceGUI Dashboard

Run the headless controller with the new single-chat NiceGUI UI:

```
python C:\Users\codym\AgenticConsole\dashboard.py
```

This launches one chat interface. The controller decides which tools to use and runs the plan. Approvals are inline in the UI.
