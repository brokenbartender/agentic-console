from __future__ import annotations


def run_triage_pipeline(ticket: str) -> str:
    if not ticket:
        raise RuntimeError("workflow triage requires a ticket")
    lowered = ticket.lower()
    priority = "low"
    if any(k in lowered for k in ("outage", "down", "error", "billing", "security")):
        priority = "high"
    elif any(k in lowered for k in ("bug", "issue", "broken", "slow")):
        priority = "medium"
    actions = [
        f"Priority: {priority}",
        "Summarize user impact",
        "Assign owner and ETA",
        "Draft response + next step",
    ]
    return "Customer Service Triage\n\n" + "\n".join(f"- {a}" for a in actions)
