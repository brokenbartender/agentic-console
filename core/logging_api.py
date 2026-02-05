from __future__ import annotations

import json
from typing import Any, Dict

from privacy import redact_text, contains_sensitive


SCHEMA_VERSION = "v1"


def _normalize_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload)
    except Exception:
        return str(payload)


def log_audit(memory, event_type: str, payload: Any, redact: bool = True) -> None:
    raw = _normalize_payload(payload)
    if contains_sensitive(raw):
        if not redact:
            # Reject secret-class payloads at creation time when redaction is disabled.
            raise RuntimeError("Sensitive data detected in audit log payload")
    safe = redact_text(raw) if redact else raw
    memory.log_audit(event_type, safe, schema_version=SCHEMA_VERSION)


def log_debug(memory, event_type: str, payload: Any, redact: bool = True) -> None:
    raw = _normalize_payload(payload)
    if contains_sensitive(raw):
        if not redact:
            raise RuntimeError("Sensitive data detected in debug log payload")
    safe = redact_text(raw) if redact else raw
    memory.log_debug(event_type, safe, schema_version=SCHEMA_VERSION)
