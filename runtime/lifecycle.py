from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LifecycleResult:
    status: str
    run_id: str
    summary: str
    details: Dict[str, Any]


def run_lifecycle(controller, user_message: str, approve: bool = True, wait: bool = True) -> LifecycleResult:
    """Canonical agent loop: Perceive -> Plan -> Decide -> Act -> Reflect -> Persist."""
    run = controller.plan_task(user_message)
    if approve:
        controller.approve_run(run.run_id)
    if wait:
        # Wait until run completes or errors.
        while True:
            cur = controller.current_run
            if cur is None:
                break
            if cur.run_id == run.run_id and cur.status in ("complete", "error", "stopped"):
                break
            time.sleep(0.5)
    summary = controller.build_summary(run.run_id)
    return LifecycleResult(status=controller.get_run_status(run.run_id), run_id=run.run_id, summary=summary, details={})
