from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class AgentRole:
    name: str
    instructions: str


class TeamOrchestrator:
    def __init__(self, agent_chat):
        self.agent_chat = agent_chat

    def run(self, roles: List[AgentRole], task: str) -> str:
        outputs = []
        context = ""
        for role in roles:
            prompt = (
                f"Role: {role.name}\n"
                f"Instructions: {role.instructions}\n"
                f"Context so far:\n{context}\n\n"
                f"Task: {task}"
            )
            out = self.agent_chat(prompt)
            outputs.append(f"## {role.name}\n{out}")
            context += f"\n[{role.name}] {out}\n"
        return "\n\n".join(outputs)
