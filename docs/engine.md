# Headless Engine

Agentic Console now supports a headless core engine that can run without Tkinter.

## Files
- `engine.py` contains `AgentEngine` and a `run_headless` helper.

## Usage (Headless)
```powershell
python -c "from config import get_settings; from engine import run_headless; run_headless(get_settings())"
```

The UI (`app.py`) now wraps the engine and acts as a client.
