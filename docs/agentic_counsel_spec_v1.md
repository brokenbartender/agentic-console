# Agentic Counsel Spec v1

## End Goal
A local, supervised, agentic operating environment optimized for safety, auditability, determinism, and structural enforcement. The system must support plugins, multi-agent orchestration, replay, and autonomy gradients without compromising safety boundaries.

## Invariants
- All execution flows through a single, auditable executor.
- Destructive actions require explicit approval.
- Task state is persisted and recoverable.
- Memory is scoped, traceable, and redactable at creation time.
- Policy checks are mandatory for all tool calls.
- UI is a client of the orchestrator, not an alternate execution path.

## Autonomy Model
- Default mode is supervised.
- Autonomy is risk-scored and explicitly bounded by time and step budgets.
- Step-level approvals are enforced for high-risk actions.
- Autonomy never overrides safety policies.

## Safety Rules
- Path and domain allowlists are mandatory for IO and network use.
- Open-interpreter actions must be sandboxed and deny direct file/network/process access.
- Non-reversible actions must be explicitly labeled and require extra approval.
- All tool invocations are logged with typed, immutable records.
- Policy violations are recorded as structured events.

## Determinism Contract
- Every run logs model id, prompt template hash, tool versions, and environment fingerprint.
- Replay is trace-accurate and side-effect-free by default.
- Non-deterministic inputs are captured and recorded.

## Multi-Machine Contract
- Nodes have explicit roles and capability manifests.
- Planner nodes cannot execute tools.
- Executor nodes cannot plan or modify policy.
- Memory nodes are the single source of truth.
- Orchestrator is the only component allowed to dispatch work across nodes.
