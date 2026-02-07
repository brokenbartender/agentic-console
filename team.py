from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AgentRole:
    name: str
    instructions: str
    sop: str = ""
    allowed_tools: List[str] = field(default_factory=list)


class TeamOrchestrator:
    def __init__(self, agent_chat, manager_llm=None, speaker_selector_llm=None):
        self.agent_chat = agent_chat
        self.manager_llm = manager_llm or agent_chat
        self.speaker_selector_llm = speaker_selector_llm or agent_chat

    def select_next_speaker(self, roles: List[AgentRole], context: str) -> AgentRole:
        names = ", ".join([r.name for r in roles])
        prompt = (
            "Pick the next speaker based on context. Respond with exactly one role name.\n"
            f"Roles: {names}\nContext:\n{context}\n"
        )
        choice = (self.speaker_selector_llm(prompt) or "").strip()
        for r in roles:
            if r.name.lower() == choice.lower():
                return r
        return roles[0]

    def run(self, roles: List[AgentRole], task: str) -> str:
        outputs = []
        context = ""
        remaining = roles[:]
        while remaining:
            role = self.select_next_speaker(remaining, context)
            remaining = [r for r in remaining if r != role]
            sop_text = f"SOP: {role.sop}\n" if role.sop else ""
            tools_text = ""
            if role.allowed_tools:
                tools_text = f"Allowed tools: {', '.join(role.allowed_tools)}\n"
            prompt = (
                f"Role: {role.name}\n"
                f"Instructions: {role.instructions}\n"
                f"{sop_text}"
                f"{tools_text}"
                f"Context so far:\n{context}\n\n"
                f"Task: {task}"
            )
            out = self.agent_chat(prompt)
            outputs.append(f"## {role.name}\n{out}")
            context += f"\n[{role.name}] {out}\n"

            # Manager oversight (CrewAI-style)
            if self.manager_llm and role.name.lower() == "builder":
                review = self.manager_llm(
                    f"Review the builder output. If fixes needed, respond with 'FIX: <task>'.\n{out}"
                )
                if review and review.strip().lower().startswith("fix:"):
                    fix_task = review.split(":", 1)[1].strip()
                    outputs.append(f"## Manager\n{review}")
                    context += f"\n[Manager] {review}\n"
                    # Send fix to reviewer if present
                    for r in roles:
                        if r.name.lower() == "reviewer":
                            fix_prompt = f"Role: {r.name}\nInstructions: {r.instructions}\nTask: {fix_task}"
                            fix_out = self.agent_chat(fix_prompt)
                            outputs.append(f"## {r.name}\n{fix_out}")
                            context += f"\n[{r.name}] {fix_out}\n"
                            break
        return "\n\n".join(outputs)


class TwoAgentOrchestrator:
    def __init__(self, planner_chat, executor_chat):
        self.planner_chat = planner_chat
        self.executor_chat = executor_chat

    def run(self, task: str) -> str:
        plan = self.planner_chat(f"Planner: create a short plan.\nTask: {task}")
        exec_out = self.executor_chat(f"Executor: execute this plan.\nPlan:\n{plan}\nTask: {task}")
        review = self.planner_chat(f"Planner: verify success criteria and note issues.\nOutput:\n{exec_out}")
        return "\n\n".join(["## Planner Plan", plan or "", "## Executor", exec_out or "", "## Planner Review", review or ""])
class ManagerWorkerOrchestrator:
    def __init__(self, agent_chat):
        self.agent_chat = agent_chat

    def run(self, manager: AgentRole, workers: List[AgentRole], task: str) -> str:
        outputs = []
        manager_prompt = (
            f"Role: {manager.name}\nInstructions: {manager.instructions}\n"
            "You are the manager. Produce a short plan and assign work to workers.\n"
            f"Task: {task}\n"
            "Respond with a brief plan and 1-3 bullet assignments."
        )
        plan = self.agent_chat(manager_prompt)
        outputs.append(f"## {manager.name}\n{plan}")
        for worker in workers:
            tools = ", ".join(worker.allowed_tools or [])
            sop_text = f"SOP: {worker.sop}\n" if worker.sop else ""
            worker_prompt = (
                f"Role: {worker.name}\n"
                f"Instructions: {worker.instructions}\n"
                f"{sop_text}"
                f"Allowed tools: {tools}\n"
                "Execute only the manager's assignment. Do not create new tasks.\n"
                f"Manager plan:\n{plan}\n"
                f"Task: {task}"
            )
            out = self.agent_chat(worker_prompt)
            outputs.append(f"## {worker.name}\n{out}")
        review_prompt = (
            f"Role: {manager.name}\nInstructions: {manager.instructions}\n"
            "Review the worker outputs. Summarize issues or approve.\n"
            f"Outputs:\n{chr(10).join(outputs)}"
        )
        review = self.agent_chat(review_prompt)
        outputs.append(f"## {manager.name} Review\n{review}")
        return "\n\n".join(outputs)
