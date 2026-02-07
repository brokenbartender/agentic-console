# FAQ

Q: How do I run headless without the UI?
A: Use the CLI: `python runtime\run.py run "your task"`.

Q: Where are logs stored?
A: `data/agentic.log` by default. Configure `AGENTIC_LOG_FILE` to move it.

Q: How do I clear memory?
A: `python runtime\run.py memory clear`.

Q: How do I limit tools?
A: Use allowlists like `AGENTIC_ALLOWED_SHELL` and `AGENTIC_ALLOWED_MCP`.

Q: How do I switch UIs?
A: Run `dashboard.py` for NiceGUI. For the legacy UI set `AGENTIC_UI=tk` and run `app.py`.

Q: Where do run artifacts go?
A: `data/runs/<run_id>/` contains `plan.json`, `report.json`, and `summary.md`.
