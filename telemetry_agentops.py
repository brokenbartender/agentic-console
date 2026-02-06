from __future__ import annotations

import os
from typing import Any, Dict


class AgentOpsClient:
    def __init__(self) -> None:
        self._client = None
        api_key = os.getenv("AGENTOPS_API_KEY", "")
        if not api_key:
            return
        try:
            import agentops  # type: ignore

            agentops.init(api_key=api_key)
            self._client = agentops
        except Exception:
            self._client = None

    def log_event(self, trace_id: str, name: str, payload: Dict[str, Any]) -> None:
        if not self._client:
            return
        try:
            self._client.record(event=name, properties={"trace_id": trace_id, **payload})
        except Exception:
            return
