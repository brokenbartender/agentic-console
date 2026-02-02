from __future__ import annotations

from typing import List


class DeepResearch:
    def __init__(self, agent_chat, rag_search):
        self.agent_chat = agent_chat
        self.rag_search = rag_search

    def run(self, question: str) -> str:
        # Plan
        plan = self.agent_chat(f"Create a concise research plan (3-5 steps) for: {question}")
        # Retrieve
        evidence = self.rag_search(question, limit=5)
        ev_text = "\n".join(f"- {e['source']}: {e['text'][:200]}" for e in evidence)
        # Draft
        draft = self.agent_chat(
            f"Use the evidence to answer the question. Evidence:\n{ev_text}\n\nQuestion: {question}"
        )
        # Reflect
        critique = self.agent_chat(
            f"Critique the draft for missing evidence, uncertainty, and errors.\nDraft:\n{draft}"
        )
        # Revise
        final = self.agent_chat(
            f"Revise the draft using the critique.\nCritique:\n{critique}\n\nDraft:\n{draft}"
        )
        return f"Plan:\n{plan}\n\nAnswer:\n{final}"
