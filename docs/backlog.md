# Backlog

## Consciousness Stack (Scored)
Scores are 1-10. Higher impact = more benefit. Higher effort/risk = more cost.

1. Generative Agents — Reflection & Insight
- Impact: 8
- Effort: 4
- Risk: 3
- Notes: Nightly reflection job; fits existing memory + dreaming loops.
- Priority: P1

2. LangGraph — Persistence / Checkpointing
- Impact: 8
- Effort: 5
- Risk: 3
- Notes: Save/restore agent state for long-running cognition.
- Priority: P1

3. MemGPT (Letta) — Core/Recall Memory Split
- Impact: 9
- Effort: 6
- Risk: 5
- Notes: Core memory + recall memory + self-edit tool with policy guardrails.
- Priority: P1

4. Voyager — Skill Library
- Impact: 8
- Effort: 5
- Risk: 4
- Notes: Auto-save successful functions, index for reuse.
- Priority: P1

5. Self-Refine — Critique Loop
- Impact: 6
- Effort: 3
- Risk: 2
- Notes: Generate → critique → refine; low risk, quick win.
- Priority: P1

6. Agentic Memory — Working/Episodic/Semantic
- Impact: 7
- Effort: 5
- Risk: 4
- Notes: Formalize memory types and routing.
- Priority: P2

7. MetaGPT — Planner/Doer/Critic SOPs
- Impact: 7
- Effort: 6
- Risk: 5
- Notes: Use for high-risk tasks only to reduce overhead.
- Priority: P2

8. BabyAGI — Dynamic Task Prioritization
- Impact: 6
- Effort: 4
- Risk: 4
- Notes: Internal reprioritization of task queue.
- Priority: P2

9. DSPy — Prompt Self-Optimization
- Impact: 7
- Effort: 7
- Risk: 6
- Notes: Keep in sandboxed evals to avoid prompt drift.
- Priority: P3

10. The Consciousness AI (ACM) — GWT + Emotional Variables
- Impact: 6
- Effort: 6
- Risk: 7
- Notes: Treat emotional variables as telemetry first, not control drivers.
- Priority: P3

## UI Feature Backlog (Pro Chat + Control Plane)
1. Editable Config Sheet (Shadcn-style)
- Priority: P1
- Notes: Add POST /api/config to update settings; include validation + restart toggle.

2. NiceGUI Floating Companion: Always-on-top + Activity Pulse
- Priority: P1
- Notes: Add window flags for always-on-top, pulse indicator on task run.

3. Terminal Stream: Full stdout/stderr
- Priority: P1
- Notes: Stream sandbox_run output line-by-line into UI.

4. Sources Cards: Favicon + file link cards
- Priority: P2
- Notes: Render RAG sources as rich cards with path/preview.

5. Graph View: True pan/zoom + node drag
- Priority: P2
- Notes: Upgrade SVG to canvas interactions.
