from __future__ import annotations

from typing import Dict, Any


class MCPAdapter:
    def __init__(self) -> None:
        self.providers = {}

    def register(self, name: str, provider) -> None:
        self.providers[name] = provider

    def call(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self.providers:
            raise RuntimeError(f"Unknown MCP provider: {name}")
        return self.providers[name](payload)
