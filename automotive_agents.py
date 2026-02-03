def ownership_companion_prompt(task: str) -> str:
    return (
        "You are an ownership companion agent for vehicle owners. "
        "Help with proactive service reminders, feature discovery, and vehicle health. "
        "Focus on clear, actionable guidance.\n\n"
        f"Task: {task}"
    )


def dealer_assist_prompt(task: str) -> str:
    return (
        "You are a dealer assist agent for sales and service teams. "
        "Automate routine workflows, draft customer-facing messages, and summarize vehicle info. "
        "Keep outputs concise and operational.\n\n"
        f"Task: {task}"
    )


def mobile_work_prompt(task: str) -> str:
    return (
        "You are a mobile work agent integrated with calendars and messaging. "
        "Provide hands-free summaries, prep, and navigation-aware reminders. "
        "Prefer short, voice-friendly responses.\n\n"
        f"Task: {task}"
    )


def audio_ai_checklist() -> str:
    items = [
        "Multi-speaker separation accuracy in noisy cabin",
        "Multi-zone routing (driver vs passenger channels)",
        "Noise reduction under highway and rain conditions",
        "Emergency vehicle detection sensitivity/false positives",
        "Wake-word robustness with open windows",
        "Latency budget (end-to-end < 250ms)",
        "Power efficiency under continuous listening",
        "Fallback to offline ASR when connectivity drops",
    ]
    lines = ["Audio AI Checklist", ""]
    lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)
