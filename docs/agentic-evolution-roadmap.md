# Agentic Evolution Roadmap (2025/2026)

This roadmap translates the provided architectural framework into staged, codebase-specific milestones for Agentic Console.

## Phase 1: Cognitive Architecture (Brain)
- [x] Add `workflows/` module for deterministic pipelines.
- [ ] Implement workflow-vs-agent routing gate.
- [x] Add System 2 slow-mode (multi-pass deliberate reasoning).
- [x] Implement Diversity of Thoughts (DoT) ensemble chooser.
- [ ] Add Evaluator-Optimizer loop for code/debug tasks.

## Phase 2: Advanced Memory (Hippocampus)
- [ ] Working memory stack (short-term task context).
- [ ] Archival memory summaries (compressed descriptors).
- [ ] Procedural memory registry integration.
- [x] GraphRAG schema (entity/edge tables).
- [x] Hybrid retrieval: vector + graph traversal.

## Phase 3: Sensory Perception (Senses)
- [x] Perception aggregator F (baseline screenshot/metadata).
- [ ] Unified multimodal embedding interface.
- [ ] Optional wake-word listener (opt-in).

## Phase 4: Tooling & Execution (Hands)
- [x] MCP resources/prompts support in adapter.
- [ ] Tool schema validation + argument normalization (poka-yoke).
- [ ] Sandboxed execution for generated code.

## Phase 5: Swarm Collaboration (Team)
- [ ] Agent-as-tool call pattern.
- [ ] Fan-out limit (<= 5) enforcement.
- [ ] Reference-based messaging artifacts.

## Phase 6: Governance & Safety (Guardrails)
- [x] Data constitution file + pre-ingest checks.
- [x] Parallel safety screening (sectioning pattern).
- [ ] PII redaction pipeline (optional).
- [ ] Confidence calibration hooks + UQ tracking.

## Phase 7: Self-Evolution (Growth)
- [ ] Reflexion loop in core agent responses.
- [ ] Prompt/agent variant archive with scoring.
- [ ] Meta-agent scaffolding for ADAS/DGM experiments.

## Phase 8: Business/Micro-SaaS (Money)
- [ ] Market research agent (trends/sentiment pipeline).
- [ ] RaaS pricing model support.

## Phase 9: UI (Dashboard)
- [ ] Fishbowl UI panel (what/why/using).
- [ ] Granular HITL checkpoints.

## Phase 10: Infrastructure (Plumbing)
- [ ] Hybrid model router by cost/latency/complexity.
- [ ] Self-healing retries + fallback policy.
- [ ] End-to-end trace IDs and observability.
