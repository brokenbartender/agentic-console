from __future__ import annotations


def run_content_pipeline(topic: str) -> str:
    if not topic:
        raise RuntimeError("workflow content requires a topic")
    steps = [
        f"Define audience + goal for: {topic}",
        "Draft outline (3-5 sections)",
        "Write core content",
        "Repurpose into 3 channels (LinkedIn, X, newsletter)",
        "Add CTA and publish checklist",
    ]
    return "Content Pipeline\n\n" + "\n".join(f"- {s}" for s in steps)
