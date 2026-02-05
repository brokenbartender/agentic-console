# Agentic-Console Perfection Plan
A safety-first, local intelligence operating system with auditability and determinism.

## Phase 1 — Freeze Reality & Define the Contract (Execute Now)
- Update `docs/current_state.md` to match the actual repo.
- Update `docs/agentic_counsel_spec_v1.md` with invariants + multi-machine contract.
- Update `docs/architecture_layers.md` with current state + target enforcement.
Outcome: ground truth and target truth are locked.

## Phase 2 — Create/Confirm the Architecture Skeleton (Already Present)
- `core/`, `orchestrator/`, `executor/`, `ui/`, `plugins/` exist.
- `core/layers.py`, `core/container.py`, `core/schemas.py`, `core/logging_api.py` exist.
- `executor/files.py`, `executor/shell.py`, `executor/execute.py` exist.
Outcome: the repo has a spine; now we enforce it.

## Phase 3 — Seal All Bypasses
- Ensure all tool execution routes through `executor.execute.execute_tool`.
- Block direct file IO and subprocess outside `executor/` (import-lint + tests).
- Sandbox `open-interpreter` so it cannot read/write disk, run subprocess, or open network.
Outcome: safety becomes structural, not optional.

## Phase 4 — Real Orchestrator State Machine
- Make `OrchestratorState` the only allowed state.
- Validate every transition in one place.
- Persist run state and reload on restart.
- Enforce: plan → approve → execute + step-level approvals.
Outcome: approvals, pause, stop, and recovery are reliable.

## Phase 5 — Typed Event Ledger & Audit Trail
- Adopt `ToolCall`, `TaskEvent`, `PolicyViolation`, `RunHeartbeat` schemas.
- Write audit logs through `core/logging_api` only.
- Redact at creation time, reject secrets.
- Separate audit vs debug retention.
Outcome: you can prove what happened.

## Phase 6 — Memory 2.0 (Traceable, Scoped, Safe)
- Wire `memory_refs` to run/step/tool.
- Enforce scope (shared/private) and quarantine.
- Add TTL + pruning jobs + indices.
Outcome: memory becomes a safe second brain.

## Phase 7 — Transactions, Rollback & Snapshots
- Add transaction journal + two-phase markers.
- Snapshot files + DB before multi-step runs.
- Label non-reversible actions and require extra approval.
Outcome: multi-step actions are survivable.

## Phase 8 — Replay & Determinism
- Store model id, prompt hash, tool versions, env fingerprint, nondet inputs.
- Add replay mode that reproduces actions without side effects.
Outcome: debugging becomes deterministic.

## Phase 9 — Plugins & Workflows (Safe Mode)
- Add plugin loader with manifest + denylist.
- Capability declarations and sandboxed imports.
- Workflow execution under same policy gate.
Outcome: extensibility without chaos.

## Phase 10 — Multi-Machine Intelligence System
- Explicit node roles (Planner/Executor/Memory/UI).
- Signed message bus; orchestrator dispatch only.
- Central memory + audit trail.
- Failover + reassign tasks.
Outcome: one system, many machines, zero chaos.

---

## Execution Order
1. Phase 1 docs (done in this step).
2. Phase 2 confirm skeleton (already present).
3. Phase 3 enforcement.
4. Phase 4–10 in order.
