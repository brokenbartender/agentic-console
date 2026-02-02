# Agentic Console

Local native agentic assistant with a Tkinter UI and web UI.

## Features
- Natural language (no commands required)
- Tool registry with confirmations for destructive actions
- Planner / Executor / Verifier orchestration
- Short + long memory with local vector search
- Local Ollama fallback when OpenAI is unavailable
- Task queue (serializes actions)
- Metrics endpoint for quick health checks
- RAG indexing + evidence retrieval
- Deep Research workflow with reflection
- Multimodal OCR hook (optional)

## Run
```powershell
python app.py
```
Web UI: `http://127.0.0.1:8333`

## Commands
- `index <path>`: index a file or directory
- `rag <query>`: answer with evidence + confidence
- `deep_research <question>`: plan + reflect + answer
- `ocr <pdf>`: quick OCR preview (requires tesseract)

## Environment
Create a `.env` in the project root:
```
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.1
OLLAMA_MODEL=phi3:latest
OLLAMA_BASE=http://127.0.0.1:11434
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

Optional:
```
AGENTIC_EMBEDDING_DIM=256
AGENTIC_SHORT_MEMORY_TTL=86400
AGENTIC_LONG_MEMORY_TTL=2592000
AGENTIC_WEB_PORT=8333
```

## Endpoints
- `GET /health` => `ok`
- `GET /api/metrics` => JSON metrics
- `POST /api/command` => send a command

## Tests
```powershell
python -m unittest discover -s tests
python evals/run_evals.py
```
