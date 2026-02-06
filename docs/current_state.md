**Repository Structure & Layering**  
1. A **layer map exists** in `core/layers.py` (LAYER_EDGES); enforcement is partial via `tests/test_enforcement.py` (no subprocess/shutil/tools.execute outside executor).  
2. `core/`, `orchestrator/`, `executor/`, `ui/`, `plugins/` directories exist; **UI logic still lives in `app.py`** and `ui/` is empty.  
3. `core/container.py`, `core/schemas.py`, `core/logging_api.py` exist as **Phase‑2 placeholders**, but there is **no dependency injection wiring** yet.  
4. **No boundary enforcement** prevents `app.py` or other modules from importing across layers.  
5. `workflows/` remain unrestricted; **no structural rule** prevents workflow code from importing tools or executor.  
6. Global state mutation is still possible anywhere (e.g., in `app.py`, `metrics`, logging).  
7. External library imports are unrestricted; there is no allowlist.  
8. Runtime configuration is still defined in `config.py` (`Settings` + `_load_dotenv`); no enforcement prevents bypass.  
9. The repo already includes Phase‑2 files (`executor/files.py`, `executor/shell.py`, `executor/execute.py`, `orchestrator/state.py`).  
10. There is no CI rule to enforce the layer map; tests provide partial enforcement only.  

**Orchestrator Control Flow & State**  
1. `orchestrator/state.py` defines `OrchestratorState` and `validate_transition` (now allows `PLANNED/APPROVED -> STOPPED`).  
2. `AgentApp._set_run_status()` centralizes state transitions and persists them to SQLite.  
3. Task submission entry points remain `AgentApp.run_command()` (UI) and `/api/command` (HTTP).  
4. `TaskQueue` still serializes actions in a single daemon thread (FIFO).  
5. `step_approval` is implemented via `step_approval_event` and **blocks each step** when enabled.  
6. Run state is **persisted to SQLite** via `memory.create_task_run` / `update_task_run`.  
7. The app now **rehydrates the last run** from SQLite on startup (`_load_last_run`).  
8. Pause/stop are cooperative, but now **update run status** (`PAUSED`, `STOPPED`).  
9. Approval gates exist in both UI and API (`/api/approve`, `/api/approve_step`).  
10. There is no multi‑run concurrency policy beyond the single TaskQueue worker.  

**Agent Lifecycle & Authority Boundaries**  
1. Agents implement `PlannerAgent.plan`, `RetrieverAgent.retrieve`, `ExecutorAgent.run`, `VerifierAgent.verify` in `agents.py`.  
2. Agents are instantiated once in `AgentApp.__init__`; no teardown or restart lifecycle.  
3. `open‑interpreter` is configured in `_agent_chat_base`; **no hard sandbox** beyond prompts.  
4. `policy.requires_confirmation` is applied to tool calls via `executor.execute`, **not** to open‑interpreter actions.  
5. Tools execute via `_execute_tool` → `executor.execute.execute_tool`.  
6. `TeamOrchestrator` and `A2ABus` do not enforce permissions; they coordinate only.  
7. Workflow execution (`workflow <name>`) is not gated by policy beyond tool allowlists.  
8. There is no structural prevention of threads/subprocesses from agent code.  
9. Agent identities are implicit; no persistent identity store beyond memory tables.  
10. Agent authority boundaries are still policy‑by‑convention.  

**Task Representation & Execution Semantics**  
1. Canonical task schema is still `TaskRun` + `PlanStep` in `app.py`.  
2. Plans are **linear only** (no branching).  
3. Plan editing is free‑form; no schema validation beyond re‑planning.  
4. Step budget enforced by `settings.max_plan_steps` and tool call budget by `settings.max_tool_calls_per_task`.  
5. Failures stop execution and set status to `ERROR`; recovery is manual.  
6. Command parsing happens in `_execute_step`; execution in `_execute_tool`.  
7. Long‑running tasks are tracked in `jobs` table but no resume logic exists.  
8. `TaskRun` is persisted in `task_runs` table, but not reloaded for resume.  
9. Proof pack generation exists (`_start_proof_pack`, `_write_summary`).  
10. Task events are logged in `events` (not typed beyond JSON).  

**Memory Schema, Retention, and Auditability**  
1. SQLite schema includes `events`, `audit_logs`, `debug_logs`, `memories`, `memory_refs`, `task_runs`, `transactions`, `run_context`, `nondet_inputs`, `model_runs`, and more.  
2. `memory_refs` is now **wired** when memory entries are created (run_id + step_id).  
3. Memory scope + quarantine columns exist in `memories` (`scope`, `status`, `quarantine_reason`) and are validated on write.  
4. TTL is supported via `expires_at`; a background prune loop now enforces expiry.  
5. Audit logs are written via `core/logging_api.log_audit` with **redaction + sensitive‑data reject** at creation time.  
6. Memory redaction is enforced at write time in `MemoryStore.add_memory` (sensitive content is redacted).  
7. `run_context` and `nondet_inputs` are recorded; used for determinism traces.  
8. Explicit indexes exist for `events.timestamp`, `memories.expires_at`, and `rag_chunks.source`.  
9. No conflict‑resolution logic exists beyond status fields.  
10. Memory is local‑only; no remote store.  

**Tool Execution & Sandboxing**  
1. `executor/execute.execute_tool` is the **only allowed tool entrypoint**; `ToolRegistry.execute` now rejects calls without `ToolContext(via_executor=True)`.  
2. File mutations go through `executor/files.py` in tool handlers; new enforcement tests forbid `shutil` outside executor.  
3. Subprocess calls are centralized in `executor/shell.py`; enforcement tests forbid `subprocess` elsewhere.  
4. Allowlists enforced in `tools.py` via `privacy.is_path_allowed` / `is_domain_allowed`.  
5. `open‑interpreter` is forced into **text‑only** mode by default (`AGENTIC_OI_MODE=text_only`), but can still be loosened by config.  
6. Dry‑run returns a string and is logged as a `tool_call` audit event (with `dry_run=True`).  
7. Undo uses `memory.kv['last_trash']`; no authentication or multi‑step rollback.  
8. Exceptions are surfaced to UI; no error taxonomy.  
9. `_execute_tool` records typed `ToolCall` to audit log.  
10. `sandbox.run_python` only enforces timeout + temp dir; no CPU/RAM limits.  

**Policy Enforcement & Safety Guarantees**  
1. `policy.requires_confirmation` is used by `executor.execute` and `tools.py` for destructive actions.  
2. `demo_mode` blocks `delete` and `move` in `tools.py`; other paths are not blocked.  
3. `safety.py` is used for screening text but does not gate execution.  
4. Allowed paths/domains are configured in `.env` and parsed by `privacy.py`.  
5. Step approvals are enforced in `_run_task_run` when enabled.  
6. Policy violations are not a first‑class log event type yet.  
7. Plan approval is enforced via `/api/approve` and `approve_run`.  
8. Autonomy level affects confirmation requirements; no broader risk scoring.  
9. Open‑interpreter bypass remains the major safety gap.  
10. No kill‑switch or global policy overrides exist.  

**Logging, Replay, and Determinism**  
1. `audit_logs` and `debug_logs` tables exist; `log_audit` redacts and rejects sensitive payloads if redaction is disabled.  
2. `TaskEvent` audit records are emitted via `_log_event` (typed payloads).  
3. `RunHeartbeat` audit records are emitted at run start and completion.  
4. `run_context` logs model id, prompt hash, tool versions, and env fingerprint.  
5. `nondet_inputs` captures time and other nondeterministic inputs (used in `app.py`).  
6. Replay mode exists as `AGENTIC_REPLAY_MODE`; `_execute_tool` forces `dry_run` when enabled.  
7. UI logs are still in `self.log_buffer` + Tkinter widget; `events` is separate.  
8. Retention now applies to `events`, `audit_logs`, and `debug_logs` (separate settings).  
9. No replay orchestrator exists; only dry‑run gating.  
10. No end‑to‑end trace IDs across runs.  

**Plugin & Extensibility Boundaries**  
1. `plugins/` directory exists but **no loader** or manifest parser yet.  
2. MCP integration exists (`mcp_adapter.py`), with auth via env tokens only.  
3. Workflows are deterministic functions with no additional policy gates.  
4. No capability declarations or sandboxed plugin import loader.  
5. No plugin failure isolation or versioning.  
6. No kill‑switch mechanism for plugins/providers.  
7. Tool registry is static in `tools.py`.  
8. Plugins cannot currently bypass policy because they are not loaded.  
9. No remote agent support in code.  
10. Extensibility remains ad‑hoc.  

**UI ↔ Backend Contract**  
1. UI is Tkinter in `app.py`; HTTP server is `ThreadingHTTPServer` in `app.py`.  
2. API endpoints: `/api/command`, `/api/approve`, `/api/approve_step`, `/api/metrics`, `/api/trace`, `/api/jobs`, `/api/models`, `/api/a2a`.  
3. JSON schemas are implicit; no validation layer.  
4. UI state is derived from `self.current_run` and in‑memory flags; DB is secondary.  
5. Errors are returned as plain text or logs; no structured error schema.  
6. Approvals are unauthenticated.  
7. Plan editing is re‑planning; no backend schema validation.  
8. Concurrency is serialized by `TaskQueue`.  
9. Tool execution still flows through `_execute_tool` → `executor.execute`.  
10. UI does not enforce authentication or user identity scopes.
