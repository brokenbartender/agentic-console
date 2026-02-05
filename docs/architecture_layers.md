# Architecture Layers

## Layer Map
- ui: presentation and user input only
- orchestrator: task state, approvals, scheduling, and lifecycle
- executor: tool execution, sandboxing, and side-effect control
- core: config, schemas, policy, memory, logging
- plugins: external capability providers

## Current State
- `core/layers.py` defines the map, but **no enforcement** exists yet.
- `ui/` is empty; UI and HTTP server live in `app.py`.
- `executor/` and `orchestrator/` contain minimal scaffolding used by `app.py`.

## Import Rules (Target)
- ui may import orchestrator only
- orchestrator may import executor and core
- executor may import core only
- core must not import ui, orchestrator, executor, or plugins
- plugins may import core interfaces only

## Choke Points (Target)
- All tool execution must pass through executor entrypoints
- All policy checks must pass through core policy gate
- All writes must pass through executor/file APIs
- All subprocess calls must pass through executor/shell APIs

## Enforcement (Planned)
- Add import-linter rules for allowed edges
- Add tests that fail on direct subprocess or file writes outside executor
- Add CI checks that validate layer map compliance
