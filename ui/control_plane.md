# Agentic Control Plane UI (Phase 1)

## Targets (First 5)
1. Open WebUI (Artifacts panel)
2. Flowise or LangFlow (Graph canvas)
3. Rivet (Live execution tracing)
4. AgentOps (Session replay + cost)
5. NiceGUI (Always-on-top desktop companion)

## Status
- AgentOps: integrated in `telemetry_agentops.py` (optional)
- Remaining UIs: launch scripts + placeholder adapters added

## Next Actions
- Decide Flowise vs LangFlow
- Pick Open WebUI deployment target (Docker vs local)
- Wire UI auth + run URLs into `ui_registry.json`
