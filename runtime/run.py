from __future__ import annotations

import argparse
import json
import os
import platform
import sys

from controller import HeadlessController
from config import get_settings
from runtime.lifecycle import run_lifecycle


def cmd_run(args) -> None:
    ctrl = HeadlessController()
    if args.two_agent:
        report = ctrl.run_two_agent(args.message, max_loops=2)
        print(json.dumps(report.__dict__, indent=2, default=str))
        return
    res = run_lifecycle(ctrl, args.message, approve=not args.no_approve, wait=True)
    print(res.summary)


def cmd_agent(args) -> None:
    ctrl = HeadlessController()
    data = ctrl.describe_agent()
    if args.sub == "status":
        print(json.dumps(data.get("status", {}), indent=2))
        return
    if args.sub == "tools":
        print(json.dumps(data.get("tools", []), indent=2))
        return
    print(json.dumps(data, indent=2))


def cmd_memory(args) -> None:
    ctrl = HeadlessController()
    if args.sub == "show":
        print(json.dumps(ctrl.memory_snapshot(), indent=2))
        return
    if args.sub == "search":
        results = ctrl.search_memory(args.query)
        print(json.dumps(results, indent=2))
        return
    if args.sub == "pin":
        ctrl.pin_memory(args.text)
        print("Pinned.")
        return
    if args.sub == "clear":
        ctrl.clear_memory()
        print("Memory cleared.")
        return
    if args.sub == "edit":
        ctrl.edit_profile(args.key, args.value)
        print("Profile updated.")
        return


def cmd_workflow(args) -> None:
    ctrl = HeadlessController()
    if args.sub == "list":
        print(json.dumps(ctrl.list_workflows(), indent=2))
        return
    if args.sub == "run":
        output = ctrl.run_workflow(args.path, args.goal or "")
        print(output)
        return
    if args.sub == "create":
        output = ctrl.save_workflow(args.name)
        print(output)
        return


def cmd_doctor(_args) -> None:
    settings = get_settings()
    checks = []

    def add_check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    add_check("python", True, f"{platform.python_version()} ({sys.executable})")
    add_check("platform", True, f"{platform.system()} {platform.release()}")
    add_check("data_dir", os.path.isdir(settings.data_dir), settings.data_dir)
    add_check("log_file", os.path.exists(settings.log_file), settings.log_file)
    add_check("memory_db", os.path.exists(settings.memory_db), settings.memory_db)
    add_check("OPENAI_API_KEY", bool(os.getenv("OPENAI_API_KEY")), "set" if os.getenv("OPENAI_API_KEY") else "missing")
    ollama_model = os.getenv("OLLAMA_MODEL") or settings.ollama_model
    add_check("OLLAMA_MODEL", bool(ollama_model), ollama_model or "missing")
    ui_build = os.path.join(os.getcwd(), "ui", "control_plane", "index.html")
    add_check("ui_build", os.path.exists(ui_build), ui_build)
    host = os.getenv("AGENTIC_WEB_HOST", str(settings.server_host))
    port = os.getenv("AGENTIC_WEB_PORT", str(settings.server_port))
    add_check("web", True, f"http://{host}:{port}")

    for name, ok, detail in checks:
        status = "OK" if ok else "WARN"
        print(f"{status:<5} {name:<14} {detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agentic", description="Agentic Console Runtime")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run a task")
    run.add_argument("message", help="User message")
    run.add_argument("--no-approve", action="store_true", help="Do not auto-approve")
    run.add_argument("--two-agent", action="store_true", help="Use two-agent loop")
    run.set_defaults(func=cmd_run)

    agent = sub.add_parser("agent", help="Agent introspection")
    agent_sub = agent.add_subparsers(dest="sub", required=False)
    agent_sub.add_parser("describe")
    agent_sub.add_parser("status")
    agent_sub.add_parser("tools")
    agent.set_defaults(func=cmd_agent)

    memory = sub.add_parser("memory", help="Memory utilities")
    mem_sub = memory.add_subparsers(dest="sub", required=True)
    mem_sub.add_parser("show")
    search = mem_sub.add_parser("search")
    search.add_argument("query")
    pin = mem_sub.add_parser("pin")
    pin.add_argument("text")
    mem_sub.add_parser("clear")
    edit = mem_sub.add_parser("edit")
    edit.add_argument("key")
    edit.add_argument("value")
    memory.set_defaults(func=cmd_memory)

    wf = sub.add_parser("workflow", help="Workflow utilities")
    wf_sub = wf.add_subparsers(dest="sub", required=True)
    wf_sub.add_parser("list")
    runwf = wf_sub.add_parser("run")
    runwf.add_argument("path")
    runwf.add_argument("--goal")
    createwf = wf_sub.add_parser("create")
    createwf.add_argument("name")
    wf.set_defaults(func=cmd_workflow)

    doctor = sub.add_parser("doctor", help="Check environment health")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
