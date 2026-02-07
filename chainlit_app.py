from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import chainlit as cl

from config import get_settings
from engine import AgentEngine
from a2a import A2ABus
from controller import HeadlessController


settings = get_settings()
engine = AgentEngine(settings)
engine.start_a2a()
ctrl = HeadlessController()


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


async def _event_stream() -> None:
    last_ts = 0.0
    while True:
        try:
            events = engine.memory.get_recent_events(20)
            for ev in reversed(events):
                ts = float(ev.get("timestamp", 0))
                if ts <= last_ts:
                    continue
                last_ts = ts
                etype = ev.get("type") or ev.get("event_type")
                payload = ev.get("payload")
                if etype == "agent_handoff" and isinstance(payload, dict):
                    role = payload.get("role") or "Agent"
                    tools = payload.get("tools") or []
                    await cl.Message(content=f"Agent handoff: **{role}**\nTools: {', '.join(tools)}").send()
                    continue
                if etype == "ui_block" and isinstance(payload, dict):
                    ui_block = payload.get("ui") or {}
                    kind = ui_block.get("type")
                    if kind == "image":
                        src = ui_block.get("src") or ui_block.get("path") or ""
                        if src:
                            await cl.Message(
                                content=ui_block.get("caption", "Image"),
                                elements=[cl.Image(path=src, name="image")],
                            ).send()
                            continue
                    if kind == "toast":
                        await cl.Message(content=ui_block.get("message", "")).send()
                        continue
                    if kind == "form":
                        fields = ui_block.get("fields") or []
                        cl.user_session.set("pending_form", ui_block)
                        cl.user_session.set("pending_form_fields", fields)
                        cl.user_session.set("pending_form_values", {})
                        cl.user_session.set("pending_form_idx", 0)
                        title = ui_block.get("title", "Form")
                        await cl.Message(content=f"{title}: I'll ask for each field.").send()
                        if fields:
                            f0 = fields[0]
                            label = f0.get("label") or f0.get("key") or f0.get("name") or "field"
                            placeholder = f0.get("placeholder") or ""
                            prompt = f"{label}"
                            if placeholder:
                                prompt += f" ({placeholder})"
                            await cl.AskUserMessage(content=prompt).send()
                        else:
                            await cl.Message(content="No fields provided.").send()
                        continue
                    if kind == "diff":
                        diff_text = ui_block.get("diff") or ""
                        if diff_text:
                            await cl.Message(content="Diff:").send()
                            await cl.Message(content=f"```diff\n{diff_text}\n```").send()
                        continue
                    if kind == "timeline":
                        items = ui_block.get("items") or []
                        lines = [f"- {i}" for i in items]
                        await cl.Message(content="Timeline:\n" + "\n".join(lines)).send()
                        continue
                await cl.Step(name="Event", type="tool").send(
                    output=json.dumps({"type": etype, "payload": payload}, indent=2)
                )
        except Exception:
            pass
        await cl.sleep(2)


@cl.on_chat_start
async def start() -> None:
    cl.user_session.set("started", True)
    await cl.Message(content="Mission Control ready.").send()
    cl.user_session.set("a2a_task", cl.create_task(_a2a_stream()))
    cl.user_session.set("event_task", cl.create_task(_event_stream()))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = message.content.strip()
    pending_form = cl.user_session.get("pending_form")
    if pending_form:
        # If user already sent JSON, accept it.
        if text.startswith("{") and text.endswith("}"):
            try:
                data = json.loads(text)
            except Exception:
                await cl.Message(content="Invalid JSON. Please reply with JSON like {\"field\": \"value\"}.").send()
                return
            cl.user_session.set("pending_form", None)
            cl.user_session.set("pending_form_fields", None)
            cl.user_session.set("pending_form_values", None)
            cl.user_session.set("pending_form_idx", None)
            try:
                output = ctrl.handle_command("submit_form " + json.dumps(data))
            except Exception as exc:
                output = f"Error: {exc}"
            await cl.Message(content=output or "Form submitted.").send()
            return
        fields = cl.user_session.get("pending_form_fields") or []
        values = cl.user_session.get("pending_form_values") or {}
        idx = int(cl.user_session.get("pending_form_idx") or 0)
        if idx < len(fields):
            field = fields[idx]
            key = field.get("key") or field.get("name") or field.get("label") or f"field_{idx}"
            values[key] = text
            cl.user_session.set("pending_form_values", values)
            idx += 1
            cl.user_session.set("pending_form_idx", idx)
            if idx < len(fields):
                next_field = fields[idx]
                label = next_field.get("label") or next_field.get("key") or next_field.get("name") or "field"
                placeholder = next_field.get("placeholder") or ""
                prompt = f"{label}"
                if placeholder:
                    prompt += f" ({placeholder})"
                await cl.AskUserMessage(content=prompt).send()
                return
            cl.user_session.set("pending_form", None)
            cl.user_session.set("pending_form_fields", None)
            cl.user_session.set("pending_form_idx", None)
            try:
                output = ctrl.handle_command("submit_form " + json.dumps(values))
            except Exception as exc:
                output = f"Error: {exc}"
            await cl.Message(content=output or "Form submitted.").send()
            return
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

    try:
        output = ctrl.handle_command(text)
    except Exception as exc:
        output = f"Error: {exc}"
    await cl.Message(content=output or "OK").send()
