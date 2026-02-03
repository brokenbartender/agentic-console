def agentic_pillars_summary() -> str:
    items = [
        "Perception: sense inputs from environment.",
        "Reasoning: detect patterns and draw conclusions.",
        "Planning: chart paths under constraints.",
        "Learning: improve from feedback over time.",
        "Verification: validate reasoning before action.",
        "Execution: act on plans with precision.",
    ]
    lines = ["Agentic Pillars", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)


def vertical_agent_templates() -> str:
    items = [
        "Healthcare: diagnostics, patient monitoring, treatment planning.",
        "Finance: fraud detection, risk assessment, trading support.",
        "Retail: personalization, inventory optimization, visual search.",
        "Education: adaptive learning, grading, tutoring assistants.",
        "Manufacturing: predictive maintenance, QC automation.",
        "Legal: contract review, research, document automation.",
        "Transportation: routing, fleet optimization, logistics.",
        "Construction: scheduling, safety monitoring, energy optimization.",
    ]
    lines = ["Vertical Agent Templates", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)
