# Phase 3 Features

## Dreaming (Semantic Consolidation)
Enable nightly consolidation:
```
AGENTIC_DREAMING=true
AGENTIC_DREAMING_HOURS=24
```

## World Loop (BDI)
```
AGENTIC_WORLD_LOOP=true
AGENTIC_WORLD_LOOP_INTERVAL=60
```

## Vision Loop (VLA)
```
AGENTIC_VISION_LOOP=true
AGENTIC_VISION_FPS=1
```
Requires: `pyautogui`, `pytesseract`.

## CFO Agent (Cost Governance)
```
AGENTIC_CFO=true
AGENTIC_CFO_MAX_TOOL_CALLS=200
AGENTIC_CFO_MAX_TOKENS=200000
```

## Debate Protocol
```
AGENTIC_DEBATE=true
```

## MCP Universal Client
```
MCP_ENDPOINTS=name=https://server/a2a
```

## Async A2A
```
AGENTIC_A2A_ASYNC=true
```

## Cockpit
Open: `http://127.0.0.1:8333/dashboard`

## Fine-Tune Export
Generate JSONL from approved runs:
```
python .\scripts\fine_tune_export.py
```
