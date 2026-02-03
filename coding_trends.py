def sdlc_shift_summary() -> str:
    items = [
        "Agent-driven implementation collapses cycle time from weeks to hours.",
        "Engineers shift from implementers to orchestrators and reviewers.",
        "Dynamic staffing: onboarding in hours, surge staffing on demand.",
        "Monitoring feeds back into rapid iteration loops.",
    ]
    lines = ["SDLC Shift Summary", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)


def oversight_scaling_checklist() -> str:
    items = [
        "Define escalation thresholds for uncertainty and high impact actions.",
        "Auto-review routine output; human review for novel or risky cases.",
        "Require checkpoints for long-running tasks.",
        "Record decisions and evidence for auditability.",
    ]
    lines = ["Oversight Scaling Checklist", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)


def security_first_checklist() -> str:
    items = [
        "Security review in every agent workflow (threat model + code scan).",
        "Limit tool access by role and purpose; require confirmation for writes.",
        "Red-team dual-use scenarios during planning.",
        "Detect prompt injection and data exfiltration attempts.",
    ]
    lines = ["Security-First Checklist", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)


def agent_surfaces_summary() -> str:
    items = [
        "Legacy languages and domain-specific automation.",
        "Non-engineering teams building internal tools.",
        "Conversational and GUI-first interfaces for domain experts.",
    ]
    lines = ["Agentic Surfaces", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)
