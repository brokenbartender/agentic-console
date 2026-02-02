# Agentic Console (Local)

Native Windows UI (Tkinter) for browser + desktop actions.

## Install

python -m pip install --upgrade pip
python -m pip install playwright pyautogui pillow open-interpreter
python -m playwright install

## Run

python app.py

## Web UI

The app also starts a local web UI at `http://127.0.0.1:8333`.
You can change it with `AGENTIC_WEB_HOST` and `AGENTIC_WEB_PORT`.

## Data + Logs

Persistent chat history and logs are stored under `data/` by default.
Override with:
`AGENTIC_DATA_DIR`, `AGENTIC_MEMORY_DB`, `AGENTIC_LOG_FILE`.

## Use

Just type what you want in natural language. No special commands required.

Notes:
- Browser uses Chrome channel if installed.
- Actions are sequential; last page persists while app is open.
- The app loads `.env` from the same folder at startup.
- OpenAI: set `OPENAI_API_KEY` and (optional) `OPENAI_MODEL`.
- Local fallback: set `OLLAMA_MODEL` and (optional) `OLLAMA_BASE` (default http://127.0.0.1:11434).
