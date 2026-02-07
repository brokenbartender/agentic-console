# Agentic Console

Agentic Console is a local agent operating system: one chat UI, a plan/execute loop, and a clear safety model.

## 5-minute demo

1. Install Python UI dependencies.

```
pip install nicegui
```

2. Build the control plane UI.

```
cd ui\control_plane_src
npm install
npm run build
```

3. Start the agent runtime.

```
python app.py
```

4. Open the control plane.

```
http://127.0.0.1:8333/dashboard
```

5. Try a quick workflow.

```
Draft a plan to audit the repo for UI regressions and summarize risks.
```

6. Approve the run, then open Artifacts, Run History, and Run Diff to compare two runs.

7. Sanity-check the environment.

```
python runtime\run.py doctor
```

## Quickstart

1. Install requirements.

```
pip install nicegui
```

2. Start the app and open `http://127.0.0.1:8333/dashboard`.

## What problem this solves

- Run complex tasks through a single chat interface.
- The planner creates a structured plan; the executor runs it.
- Approvals are required for risky actions.

## Canonical runtime

Everything runs through `runtime/run.py` and the lifecycle loop in `runtime/lifecycle.py`.

Examples:

```
python runtime\run.py run "analyze this repo and summarize risks" --two-agent
python runtime\run.py agent tools
python runtime\run.py memory show
python runtime\run.py workflow list
python runtime\run.py doctor
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

- Default UI: control plane dashboard (`/dashboard`)
- Legacy UI: set `AGENTIC_UI=tk`

## Examples

Sample prompts live in `examples/`.

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
