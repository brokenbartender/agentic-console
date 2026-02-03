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
- Purpose tagging + audit trail metadata
- Optional path/domain allowlists for tool actions
- Log redaction + event retention controls

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
- `autonomy <level>`: set autonomy (supervised|semi|autonomous)
- `purpose <text>`: set a task purpose (used in audit logs)
- `team <task>`: run a simple multi-agent team (planner/builder/reviewer)
- `jobs`: list recent jobs
- `a2a <sender -> receiver | message>`: send agent-to-agent message
- `mcp <provider | json>`: call an MCP provider (stub)

## Environment
Create a `.env` in the project root:
```
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.1
OPENAI_REASONING_MODEL=gpt-5.1
OPENAI_CODING_MODEL=gpt-5.1
OLLAMA_MODEL=phi3:latest
OLLAMA_REASONING_MODEL=phi3:latest
OLLAMA_CODING_MODEL=phi3:latest
OLLAMA_BASE=http://127.0.0.1:11434
TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

Optional:
```
AGENTIC_EMBEDDING_DIM=256
AGENTIC_SHORT_MEMORY_TTL=86400
AGENTIC_LONG_MEMORY_TTL=2592000
AGENTIC_AUTONOMY_LEVEL=semi
AGENTIC_WEB_PORT=8333
AGENTIC_ALLOWED_PATHS=C:\\Users\\codym\\Documents;C:\\Users\\codym\\Downloads
AGENTIC_ALLOWED_DOMAINS=example.com,openai.com
AGENTIC_REDACT_LOGS=true
AGENTIC_PURPOSE=General assistance
AGENTIC_EVENT_RETENTION_SECONDS=2592000
```

## Endpoints
- `GET /health` => `ok`
- `GET /api/metrics` => JSON metrics
- `GET /api/trace` => recent events
- `GET /api/jobs` => recent jobs
- `GET /api/a2a` => recent A2A messages
- `POST /api/command` => send a command

## Tests
```powershell
python -m unittest discover -s tests
python evals/run_evals.py
```
