from nicegui import ui
from controller import HeadlessController
import json

ctrl = HeadlessController()

ui.colors(primary="#3B82F6", secondary="#10B981", accent="#8B5CF6", dark="#111827")
ui.query("body").style("background-color: #0B0F19; color: #E5E7EB;")

@ui.page("/")
def main_dashboard():
    with ui.header().classes("bg-gray-900 border-b border-gray-800 p-4 items-center gap-4"):
        ui.icon("terminal", size="md").classes("text-primary")
        ui.label("AGENTIC CONSOLE").classes("font-bold text-xl tracking-wider")
        ui.space()
        with ui.row().classes("items-center gap-2"):
            ui.icon("circle", size="xs").classes("text-green-500 animate-pulse")
            ui.label("SYSTEM ONLINE").classes("text-xs font-mono text-gray-400")
        with ui.row().classes("items-center gap-2") as activity_row:
            planner_badge = ui.badge("Planner", color="blue").classes("text-xs")
            executor_badge = ui.badge("Executor", color="purple").classes("text-xs")
            verifier_badge = ui.badge("Verifier", color="gray").classes("text-xs")
            ui.button("Agent Info", on_click=lambda: show_agent_info()).props("outline")

    nudge_row = ui.row().classes("w-full bg-gray-800/60 p-2 hidden")
    nudge_label = ui.label("").classes("text-xs text-gray-200")
    nudge_action = ui.button("Diagnose", on_click=lambda: nudge_fix()).props("flat color=primary")

    with ui.row().classes("w-full h-[calc(100vh-120px)] no-wrap"):
        with ui.column().classes("w-2/3 h-full p-4 gap-4"):
            ui.label("LIVE FEED").classes("text-xs font-bold text-gray-500 mb-2")
            log_container = ui.scroll_area().classes(
                "w-full flex-grow bg-gray-900/50 rounded-lg p-4 border border-gray-800"
            )
            with ui.row().classes("w-full gap-2 items-center bg-gray-800 p-2 rounded-xl border border-gray-700"):
                input_cmd = ui.input(placeholder="Ask the agent to do anything...").classes(
                    "w-full flex-grow text-lg no-underline"
                ).props("borderless text-white")
                upload = ui.upload(on_upload=lambda e: handle_upload(e)).props('auto-upload')
                ui.button(icon="send", on_click=lambda: run_task(input_cmd.value)).props(
                    "flat round color=primary"
                )
                ui.button(icon="mic").props("flat round color=gray")

        with ui.column().classes("w-1/3 h-full border-l border-gray-800 bg-gray-900/30 p-4"):
            with ui.tabs().classes("w-full") as tabs:
                tab_plan = ui.tab("Plan")
                tab_mem = ui.tab("Memory")
                tab_runs = ui.tab("Runs")
                tab_canvas = ui.tab("Canvas")
                tab_think = ui.tab("Thinking")
            with ui.tab_panels(tabs, value=tab_plan).classes("w-full bg-transparent"):
                with ui.tab_panel(tab_plan):
                    plan_container = ui.column().classes("w-full gap-2")
                    exec_container = ui.column().classes("w-full gap-2")
                    with ui.row().classes("w-full mt-4 justify-end hidden") as approval_row:
                        ui.button("Reject", color="red", icon="close").props("outline")
                        approve_btn = ui.button("APPROVE RUN", color="green", icon="check")
                    with ui.row().classes("w-full mt-2 gap-2"):
                        ui.switch("Approve Writes", value=False, on_change=lambda e: ctrl.set_step_approval(e.value))
                with ui.tab_panel(tab_mem):
                    ui.label("Active Context").classes("text-sm font-bold")
                    ui.tree(
                        [
                            {
                                "id": "root",
                                "label": "Workspace",
                                "children": [
                                    {"id": "1", "label": "src/app.py"},
                                    {"id": "2", "label": "docs/readme.md"},
                                ],
                            }
                        ],
                        label_key="label",
                        tick_strategy="leaf",
                    )
                with ui.tab_panel(tab_runs):
                    runs_container = ui.column().classes("w-full gap-2")
                with ui.tab_panel(tab_canvas):
                    ui.label("Collaborative Canvas").classes("text-sm font-bold")
                    canvas_area = ui.textarea(placeholder="Drafts, code, notes...").classes("w-full")
                    ui.button("Save", on_click=lambda: save_canvas()).props("flat color=primary")
                with ui.tab_panel(tab_think):
                    thinking_container = ui.column().classes("w-full gap-2")

    def show_agent_info():
        info = ctrl.describe_agent()
        with ui.dialog() as dialog:
            with ui.card().classes("w-full"):
                ui.label("Agent Info")
                ui.code(json.dumps(info, indent=2)).classes("w-full")
                ui.button("Close", on_click=dialog.close)
        dialog.open()

    def render_logs():
        log_container.clear()
        with log_container:
            for entry in reversed(ctrl.activity_log):
                color = {
                    "info": "gray",
                    "error": "red",
                    "success": "green",
                    "tool": "purple",
                    "agent": "blue",
                    "event": "blue",
                    "ui": "green",
                }.get(entry["type"], "blue")
                icon = {
                    "info": "info",
                    "error": "warning",
                    "success": "check_circle",
                    "tool": "build",
                    "agent": "smart_toy",
                    "event": "bolt",
                    "ui": "dashboard",
                }.get(entry["type"], "smart_toy")
                with ui.row().classes("w-full mb-2 gap-3 items-start"):
                    ui.icon(icon).classes(f"text-{color}-400 mt-1")
                    with ui.column().classes("gap-0"):
                        ui.label(entry["message"]).classes("text-sm text-gray-200 font-mono")
                        if entry.get("details"):
                            ui.label(str(entry["details"]))
                        if isinstance(entry.get("details"), dict) and "ui" in entry["details"]:
                            render_gen_ui(entry["details"]["ui"])
                        ui.label(entry["ts"]).classes("text-[10px] text-gray-600")

    def render_gen_ui(payload: dict):
        kind = payload.get("type")
        if kind == "table":
            rows = payload.get("rows") or []
            cols = payload.get("columns") or []
            ui.table(columns=[{"name": c, "label": c, "field": c} for c in cols], rows=rows).classes("w-full")
        if kind == "cards":
            for card in payload.get("items") or []:
                with ui.card().classes("w-full p-2 bg-gray-800 border border-gray-700"):
                    ui.label(card.get("title", ""))
                    ui.label(card.get("subtitle", ""))
                    if card.get("button"):
                        ui.button(card["button"], on_click=lambda: run_task(card.get("action", ""))).props("flat color=primary")

    def render_plan():
        plan_container.clear()
        exec_container.clear()
        run = ctrl.current_run
        if not run:
            with plan_container:
                ui.label("No active plan").classes("text-gray-600 italic")
            approval_row.classes(add="hidden")
            return
        plan_schema = getattr(run, "plan_schema", None)
        if plan_schema:
            with plan_container:
                ui.label(f"Goal: {plan_schema.goal}").classes("font-bold text-primary mb-2")
                for step in plan_schema.steps:
                    with ui.card().classes("w-full p-2 bg-gray-800 border border-gray-700"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(f"{step.step_id}. {step.title}").classes("font-bold font-mono text-sm")
                            ui.badge(step.risk.upper(), color="gray" if step.risk == "safe" else "orange")
                        ui.label(f"Tool: {step.tool}").classes("text-xs text-gray-400")
                        if step.requires_confirmation:
                            ui.badge("CONFIRM", color="red")
        report = getattr(run, "report", None)
        if report:
            with exec_container:
                ui.label("Execution Report").classes("text-sm font-bold")
                ui.label(f"Status: {report.status}").classes("text-xs text-gray-400")
                for step in report.steps:
                    with ui.card().classes("w-full p-2 bg-gray-800 border border-gray-700"):
                        ui.label(f"{step.step_id}. {step.title} → {step.status}").classes("text-xs")
        if run.status == "planned":
            approval_row.classes(remove="hidden")
            approve_btn.on_click(lambda: (ctrl.approve_run(run.run_id), render_plan()))

    def render_runs():
        runs_container.clear()
        runs = ctrl.list_runs()
        for item in runs:
            with ui.card().classes("w-full p-2 bg-gray-800 border border-gray-700"):
                ui.label(item.get("run_id", ""))
                ui.label(item.get("goal", ""))
                ui.label(item.get("status", ""))
                ui.button("Fork", on_click=lambda rid=item.get("run_id", ""): fork_run(rid))

    def render_thinking():
        thinking_container.clear()
        with thinking_container:
            for entry in ctrl.activity_log[-8:]:
                ui.label(f"• {entry['message']}").classes("text-xs text-gray-400")

    def fork_run(run_id: str):
        goal = ctrl.load_run_goal(run_id)
        if goal:
            ctrl.plan_task(goal)
            render_plan()

    def render_activity():
        text_blob = " ".join([e.get("message", "") for e in ctrl.activity_log[-20:]]).lower()
        planner_active = "planning" in text_blob or "plan created" in text_blob
        executor_active = "starting execution" in text_blob or "step" in text_blob
        verifier_active = "verify" in text_blob or "verified" in text_blob
        planner_badge.props(f"color={'blue' if planner_active else 'gray'}")
        executor_badge.props(f"color={'purple' if executor_active else 'gray'}")
        verifier_badge.props(f"color={'green' if verifier_active else 'gray'}")

    def render_nudges():
        latest_error = next((e for e in reversed(ctrl.activity_log) if e.get("type") == "error"), None)
        if latest_error:
            nudge_row.classes(remove="hidden")
            nudge_label.text = "I saw an error. Want me to diagnose it?"
        else:
            nudge_row.classes(add="hidden")

    def nudge_fix():
        ctrl.plan_task("Diagnose the most recent error and propose a fix.")
        render_plan()

    def save_canvas():
        ctrl.save_canvas(canvas_area.value or "")

    def handle_upload(e):
        ctrl.log(f"Uploaded: {e.name}", type="info")

    async def run_task(text):
        if not text:
            return
        input_cmd.value = ""
        ctrl.log("Queued: " + text, type="info")
        ctrl.plan_task(text)
        render_logs()
        render_plan()
        render_runs()

    ui.timer(1.0, render_logs)
    ui.timer(1.0, render_plan)
    ui.timer(1.0, render_runs)
    ui.timer(1.0, render_thinking)
    ui.timer(1.0, render_activity)
    ui.timer(1.0, render_nudges)

def run_dashboard():
    ui.run(title="Agentic Console", dark=True, port=8333)

if __name__ == "__main__":
    run_dashboard()
