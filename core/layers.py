"""
Canonical dependency graph for Agentic-Console.
This file is intentionally minimal in Phase 1 (no enforcement yet).
"""

LAYER_EDGES = {
    "ui": ["orchestrator"],
    "orchestrator": ["executor", "core"],
    "executor": ["core"],
    "core": [],
    "plugins": ["core"],
}
