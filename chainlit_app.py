from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import chainlit as cl

from config import get_settings
from engine import AgentEngine
from a2a import A2ABus


settings = get_settings()
engine = AgentEngine(settings)
engine.start_a2a()


async def _a2a_stream() -> None:
    last_ts = 0.0
    while True:
        try:
            msgs = engine.a2a.recent(50)
            for m in reversed(msgs):
                ts = float(m.get("timestamp", 0))
                if ts <= last_ts:
                    continue
                last_ts = ts
                sender = m.get("sender")
                receiver = m.get("receiver")
                message = m.get("message")
                await cl.Step(name="A2A", type="tool").send(
                    output=f"{sender} -> {receiver}: {message}")
        except Exception:
            pass
        await cl.sleep(1)


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("started", True)
    await cl.Message(content="Mission Control ready.").send()
    cl.user_session.set("a2a_task", cl.create_task(_a2a_stream()))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = message.content.strip()
    # Risky command approval
    if any(k in text.lower() for k in ("delete", "drop", "format", "wipe", "destroy")):
        res = await cl.AskActionMessage(
            content="Risky action detected. Approve?",
            actions=[
                cl.Action(name="approve", value="yes", label="Approve"),
                cl.Action(name="deny", value="no", label="Deny"),
            ],
        ).send()
        if not res or res.get("value") != "yes":
            await cl.Message(content="Denied.").send()
            return

    # Route through existing engine/UI logic
    run = None
    try:
        run = engine.task_queue.enqueue(lambda: engine)
    except Exception:
        pass

    # Use existing AgenticConsole logic via engine memory
    reply = engine.a2a
    try:
        output = engine.a2a
        # Use app-like agent chat via dynamic import to avoid heavy UI coupling
        from app import AgentApp
        app = AgentApp.__new__(AgentApp)
        app.settings = settings
        app.engine = engine
        app.memory = engine.memory
        app.node_name = settings.node_name
        app.metrics = engine.metrics
        app.task_queue = engine.task_queue
        app.rag = engine.rag
        app.graph = engine.graph
        app.research = engine.research
        app.jobs = engine.jobs
        app.a2a = engine.a2a
        app.a2a_net = engine.a2a_net
        app._a2a_pause_path = os.path.join(settings.data_dir, "a2a_bridge_pause.json")
        app._a2a_async_enabled = False
        app.log_line = lambda _m: None
        app._memory_context = lambda: (None, None)
        app._add_message = lambda *_a, **_k: None
        app._log_event = lambda *_a, **_k: None
        app._agent_chat = AgentApp._agent_chat.__get__(app)
        app._agent_chat_base = AgentApp._agent_chat_base.__get__(app)
        output = app._agent_chat(text)
    except Exception as exc:
        output = f"Error: {exc}"

    await cl.Message(content=output).send()
