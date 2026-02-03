from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Persona:
    name: str
    goal: str
    constraints: str
    channel: str


def default_personas() -> List[Persona]:
    return [
        Persona(
            name="Speed-Seeking Operator",
            goal="Complete task in under 2 minutes",
            constraints="Low patience, minimal context",
            channel="Chat/voice",
        ),
        Persona(
            name="Risk-Aware Executive",
            goal="Ensure compliance and auditability",
            constraints="Needs approval gates and summaries",
            channel="Dashboard + reports",
        ),
        Persona(
            name="Power User",
            goal="Automate repetitive workflows",
            constraints="Wants APIs, batch, and tooling hooks",
            channel="CLI + API",
        ),
    ]


def interface_checklist() -> str:
    items = [
        "Agent-first navigation: outcomes over menus",
        "Conversational + actionable UI (run, preview, confirm)",
        "Context panel with evidence + rationale",
        "Clear safe/unsafe tool boundaries",
        "Stateful memory summary + quick corrections",
        "Fast iteration: undo, retry, and alternative paths",
    ]
    return "AI Interface Checklist\n\n" + "\n".join(f"- {i}" for i in items)


def personalization_checklist() -> str:
    items = [
        "Define personalization goal and measurable lift",
        "Guardrails: privacy, fairness, and safety constraints",
        "High-quality profile signals + consented data",
        "A/B test with synthetic users before rollout",
        "Monitor drift + feedback loops",
    ]
    return "Personalization Checklist\n\n" + "\n".join(f"- {i}" for i in items)


def ai_marketing_checklist() -> str:
    items = [
        "Publish structured, machine-readable content (schemas, APIs)",
        "Provide authoritative citations and source links",
        "Offer clear product capabilities and limitations",
        "Create model-friendly summaries and FAQs",
        "Track AI referral traffic + prompt-driven conversions",
    ]
    return "Market-To-AI Checklist\n\n" + "\n".join(f"- {i}" for i in items)


def strategic_planning_checklist() -> str:
    items = [
        "Map AI initiatives to business outcomes",
        "Allocate resources by ROI and risk profile",
        "Define KPI owners and review cadence",
        "Model infra and inference cost scenarios",
        "Keep a fast pivot loop based on data and feedback",
    ]
    return "AI Strategic Planning Checklist\n\n" + "\n".join(f"- {i}" for i in items)


def synthetic_test_prompt(scenario: str, personas: List[Persona]) -> str:
    persona_lines = []
    for p in personas:
        persona_lines.append(
            f"- {p.name}: goal={p.goal}; constraints={p.constraints}; channel={p.channel}"
        )
    personas_text = "\n".join(persona_lines)
    return (
        "You are a product reviewer. Analyze the scenario using these personas and "
        "produce: (1) top 5 friction points, (2) 3 high-impact fixes, "
        "(3) a risk note for each persona.\n\n"
        f"Scenario: {scenario}\n\nPersonas:\n{personas_text}"
    )
