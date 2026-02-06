from __future__ import annotations

import os
from typing import Any, Dict


class LangfuseClient:
    def __init__(self) -> None:
        self.enabled = False
        self._client = None
        try:
            from langfuse import Langfuse
            public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
            secret = os.getenv("LANGFUSE_SECRET_KEY", "")
            host = os.getenv("LANGFUSE_HOST", "")
            if public and secret:
                self._client = Langfuse(public_key=public, secret_key=secret, host=host or None)
                self.enabled = True
        except Exception:
            self.enabled = False

    def log_event(self, trace_id: str, name: str, payload: Dict[str, Any]) -> None:
        if not self.enabled or not self._client:
            return
        try:
            self._client.event(trace_id=trace_id, name=name, input=payload)
        except Exception:
            pass
