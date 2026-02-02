from __future__ import annotations


def requires_confirmation(tool_risk: str, autonomy_level: str) -> bool:
    level = (autonomy_level or "semi").lower()
    if tool_risk == "destructive":
        return True
    if level == "supervised":
        return True
    if level == "semi":
        return False
    if level == "autonomous":
        return False
    return True
