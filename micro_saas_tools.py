from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class Assumption:
    label: str
    value: str
    status: str
    source: str


def _normalize_status(status: str) -> str:
    lowered = (status or "").strip().lower()
    if lowered in ("verified", "confirmed", "source"):
        return "verified"
    if lowered in ("unverified", "estimate", "assumption"):
        return "unverified"
    if lowered in ("conflicting", "disputed"):
        return "conflicting"
    return "unverified"


def parse_assumption(raw: str) -> Assumption:
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) < 2:
        raise RuntimeError("assumption_add requires: label | value | status | source")
    label = parts[0]
    value = parts[1]
    status = _normalize_status(parts[2]) if len(parts) > 2 else "unverified"
    source = parts[3] if len(parts) > 3 else ""
    return Assumption(label=label, value=value, status=status, source=source)


def format_assumptions(items: List[Assumption]) -> str:
    if not items:
        return "No market assumptions saved."
    lines = ["Market Assumptions"]
    for a in items:
        src = f" source={a.source}" if a.source else ""
        lines.append(f"- {a.label}: {a.value} [{a.status}]{src}")
    return "\n".join(lines)


def roadmap_12_weeks(niche: str) -> str:
    header = f"12-Week MVP Roadmap ({niche})"
    weeks = [
        "W1: 10-15 user interviews; identify 2+ hr/day pain",
        "W2: Define 60-sec 'aha' moment + core engine outline",
        "W3: Choose stack + data sources; set success metrics",
        "W4: Build data ingestion pipeline (RAG or APIs)",
        "W5: Weekend MVP: core workflow + auth + storage",
        "W6: Agent logic + guardrails + error handling",
        "W7: UX polish; reduce steps to first value",
        "W8: Alpha with 5 users; capture aha feedback",
        "W9: Fix friction; improve latency + reliability",
        "W10: Launch landing page + reverse trial funnel",
        "W11: Public beta + community distribution",
        "W12: Billing + first paying customers",
    ]
    return header + "\n\n" + "\n".join(f"- {w}" for w in weeks)


def pricing_simulator(price: float, target_mrr: float) -> str:
    if price <= 0:
        raise RuntimeError("pricing_sim requires a positive price")
    if target_mrr <= 0:
        raise RuntimeError("pricing_sim requires a positive target MRR")
    customers = int((target_mrr / price) + (1 if target_mrr % price else 0))
    lines = [
        "Pricing Simulator",
        f"- Price: ${price:.2f}/month",
        f"- Target MRR: ${target_mrr:.2f}",
        f"- Customers needed: {customers}",
    ]
    return "\n".join(lines)


def gtm_channel_plan(niche: str) -> str:
    lines = [
        f"GTM Plan ({niche})",
        "- Primary: embedded distribution (Slack/Notion/Chrome extension)",
        "- Secondary: niche communities (Reddit/Discord/LinkedIn groups)",
        "- Tertiary: cold outbound to decision makers with 1-liner demo",
        "",
        "Assets to build:",
        "- Landing page with 60-sec demo + reverse trial CTA",
        "- 3 case studies or before/after workflows",
        "- 5-message outreach sequence",
    ]
    return "\n".join(lines)


def data_moat_prompt(niche: str) -> str:
    lines = [
        f"Data Moat Plan ({niche})",
        "- Identify 1-2 proprietary data sources (logs, docs, workflows)",
        "- Define ingestion frequency and ownership rights",
        "- Normalize into a canonical schema for RAG/fine-tuning",
        "- Add retention + consent policy",
        "- Track data coverage vs. customer outcomes",
    ]
    return "\n".join(lines)


def aha_validator(niche: str) -> str:
    lines = [
        f"Aha-Moment Validator ({niche})",
        "- What is the 60-second value moment?",
        "- How is it measured (time saved, revenue, risk reduced)?",
        "- What data is required to reach it?",
        "- What could break it (latency, missing data, errors)?",
        "- How will you prove it in week 2?",
    ]
    return "\n".join(lines)


def compliance_checklist() -> str:
    items = [
        "Data inventory + purpose limitation (GDPR)",
        "Consent + lawful basis for processing",
        "Data retention + deletion policy",
        "Model logging + explainability notes",
        "Incident response + breach notification plan",
        "EU AI Act risk categorization + human oversight",
    ]
    return "Compliance Checklist\n\n" + "\n".join(f"- {i}" for i in items)


def load_assumptions(raw: str) -> List[Assumption]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    items = []
    for item in payload:
        try:
            items.append(
                Assumption(
                    label=item.get("label", ""),
                    value=item.get("value", ""),
                    status=_normalize_status(item.get("status", "")),
                    source=item.get("source", ""),
                )
            )
        except Exception:
            continue
    return items


def dump_assumptions(items: List[Assumption]) -> str:
    return json.dumps(
        [dict(label=a.label, value=a.value, status=a.status, source=a.source) for a in items]
    )
