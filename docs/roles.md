# Roles

Agentic Console uses lightweight roles to separate planning from execution.

## Default roles

- Planner: creates a brief plan.
- Builder: executes steps and tool calls.
- Reviewer: performs final checks.

## Worker-manager mode

Some flows add a Manager role that only plans and assigns tasks to Builder roles.

## Tool restrictions

Each role can have an allowlist of tools. This is enforced during execution.
