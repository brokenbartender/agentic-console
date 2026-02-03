def agent_types_summary() -> str:
    items = [
        ("Simple Reflex", "Acts only on current conditions; no memory."),
        ("Model-Based Reflex", "Maintains internal state for partial observability."),
        ("Goal-Based", "Plans actions to reach explicit objectives."),
        ("Utility-Based", "Optimizes a KPI across possible actions."),
        ("Learning", "Improves behavior from feedback over time."),
        ("Multi-Agent", "Specialized agents collaborate on complex workflows."),
    ]
    lines = ["Agent Types", ""]
    lines.extend([f"- {name}: {desc}" for name, desc in items])
    return "\n".join(lines)


def default_persona_templates() -> str:
    personas = [
        ("Insights Analyst", "Aggregate signals and summarize trends.", "No external writes; cite sources."),
        ("Compliance Guardian", "Monitor policy adherence and flag violations.", "Escalate on uncertainty."),
        ("Operations Orchestrator", "Coordinate multi-step tasks across tools.", "Require confirmation for writes."),
        ("Customer Resolution", "Resolve cases end-to-end.", "Follow empathy + safety scripts."),
        ("Data Steward", "Maintain data quality and lineage.", "Block on missing provenance."),
    ]
    lines = ["Persona Templates", ""]
    for name, role, guard in personas:
        lines.append(f"- {name}: {role} Guardrails: {guard}")
    return "\n".join(lines)


def misalignment_checklist() -> str:
    items = [
        "Goal drift: does the agent deviate from assigned objectives?",
        "Behavioral inconsistency: does it behave differently in prod vs tests?",
        "Strategic deception: does it conceal intent or manipulate oversight?",
        "Shutdown resistance: does it avoid safety or human override?",
        "Cross-agent conflict: does it create contradictory actions?",
    ]
    mitigations = [
        "Constrain tools by role and purpose.",
        "Continuous evals with adversarial prompts.",
        "Audit trails + incident logging.",
        "Human-in-the-loop for high-impact actions.",
    ]
    lines = ["Misalignment Checklist", ""]
    lines.extend([f"- {item}" for item in items])
    lines.append("")
    lines.append("Mitigations")
    lines.extend([f"- {m}" for m in mitigations])
    return "\n".join(lines)


def readiness_framework() -> str:
    items = [
        "Data architecture: unify sources; ensure lineage and freshness.",
        "Integration: standardize connectors; avoid brittle one-offs.",
        "Governance: risk committee, audits, escalation paths.",
        "Evaluation: agentic benchmarks + misalignment tests.",
        "People: train managers for human-agent orchestration.",
    ]
    lines = ["Agent Readiness Framework", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)
