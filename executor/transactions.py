"""
Transaction scaffolding for multi-step operations.
Phase 6: two-phase markers + snapshot hooks (placeholders).
"""

from __future__ import annotations

from typing import Any, Dict


def snapshot_metadata(run_id: str, note: str = "") -> Dict[str, Any]:
    return {"run_id": run_id, "note": note}
