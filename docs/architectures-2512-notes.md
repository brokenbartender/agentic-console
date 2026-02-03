# 2512.09458v1 - Architectures for Building Agentic AI (Nowaczyk)

## Extracted guidance
- Reliability is an architectural property: component boundaries, typed interfaces, and control loops matter more than raw model capability.
- Tool routing should be permissioned with least privilege and idempotency/transactional semantics where feasible.
- Memory needs provenance + freshness, not just recall.
- Runtime governance: budgets, termination criteria, and simulate-before-actuate safeguards.
- Supervisors should log why a run stopped (budget exceeded, consensus reached, etc.).

## Applied in this repo
- Added RAG provenance fields (source_path, chunk offsets, metadata) and source ranking.
- Added `rag_sources`/`rag_rank` for explicit evidence weighting.
- Added tool call budget guard (`AGENTIC_MAX_TOOL_CALLS`).
- Added plan step budget guard (`AGENTIC_MAX_PLAN_STEPS`).
- Added `simulate` command for dry-run tool calls.
- Added `explain` command for routing + evidence visibility.

## Gaps to revisit
- Typed, schema-validated tool payloads end-to-end.
- Explicit idempotency keys and transactional tool semantics.
- Supervisor-driven termination reasons in the UI timeline.
