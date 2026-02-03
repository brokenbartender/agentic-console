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
- PDF indexing via `pypdf` (optional) with OCR fallback
- Purpose tagging + audit trail metadata
- Optional path/domain allowlists for tool actions
- Log redaction + event retention controls

## Run
```powershell
python app.py
```
Web UI: `http://127.0.0.1:8333`

## Optional Dependencies
```powershell
python -m pip install pypdf
python -m pip install pytesseract pillow pymupdf
python -m pip install pyautogui
python -m pip install openai-whisper sounddevice numpy
python -m pip install pyttsx3
```

## Commands
- `index <path>`: index a file or directory
- `rag <query>`: answer with evidence + confidence
- `rag_sources`: list indexed sources + ranks
- `rag_rank <source> <rank>`: set a source rank (0.0-2.0)
- `deep_research <question>`: plan + reflect + answer
- `ocr <pdf>`: quick OCR preview (requires tesseract)
- `simulate <tool> <args>`: dry-run a tool call without side effects
- `screenshot <path>`: capture a desktop screenshot (requires pyautogui)
- `listen [seconds]`: record audio and transcribe with Whisper (opt-in)
- `speak <text>`: text-to-speech alert (requires pyttsx3)
- `explain <query>`: show routing + memory/evidence hints
- `telemetry`: show metrics snapshot
- `autonomy <level>`: set autonomy (supervised|semi|autonomous)
- `purpose <text>`: set a task purpose (used in audit logs)
- `readiness`: show AI readiness snapshot
- `governance`: show AI governance checklist + red flags
- `data_profile <path>`: quick CSV/TSV missingness scan
- `ai_interface`: checklist for agent-native interface design
- `personalization`: checklist for generative personalization readiness
- `ai_marketing`: checklist for marketing to AI systems
- `strategy`: checklist for AI-driven planning and resource allocation
- `synthetic_test <scenario>`: synthetic user critique using personas
- `lit_review <query>`: literature summary from indexed evidence
- `analysis_plan <question>`: rigorous analysis plan template
- `ownership_companion <task>`: ownership assistant workflow
- `dealer_assist <task>`: dealership workflow assistant
- `mobile_work <task>`: voice-first mobile work helper
- `audio_ai`: audio AI checklist
- `persona_templates`: list persona templates
- `persona_add <name> | <role> | <constraints>`: save persona definition
- `personas`: list saved personas
- `agent_types`: show AI agent types
- `misalignment_check`: checklist for agent misalignment risks
- `readiness_framework`: deployment readiness checklist
- `long_run <title> | <milestones>`: track long-running agent work
- `long_run_update <id> | <status> | <note>`: update long-run status
- `long_runs`: list long-running tasks
- `oversight_rule <rule> | <severity>`: add human-oversight rule
- `oversight_rules`: list oversight rules
- `agent_team <task>`: multi-agent coding team (planner/builder/reviewer/security/QA)
- `sdlc_shift`: summary of SDLC changes with agents
- `oversight_scaling`: checklist for scaling human oversight
- `security_first`: checklist for security-first agentic coding
- `agent_surfaces`: summary of new agentic coding surfaces
- `pillars`: summarize perception/reasoning/planning/learning/verification/execution
- `vertical_agents`: list industry-specific agent templates
- `belief <text>`: store a belief (BDI)
- `beliefs`: list beliefs
- `desire <text>`: store a desire (BDI)
- `desires`: list desires
- `intention <text>`: store an intention (BDI)
- `intentions`: list intentions
- `action_space_add <name> | <description>`: register tool/action space
- `action_space_list`: list action space entries
- `action_space_remove <name>`: remove action space entry
- `checkpoint <label>`: record a safety checkpoint
- `checkpoints`: list checkpoints
- `rollback_note <id> | <notes>`: attach rollback notes
- `reflect <question>`: run draft/critique/revise loop
- `r2e_index <repo_path>`: scan repo functions for eval indexing
- `lab_note <text>`: save a lab notebook note
- `hypothesis <text>`: save a hypothesis
- `hypotheses`: list hypotheses
- `experiment <title> | <plan>`: save an experiment plan
- `experiments`: list experiments
- `experiment_update <id> | <status> | <notes>`: update experiment status
- `incident <severity> | <summary>`: log an incident
- `incidents`: list recent incidents
- `eval_run <name> | <notes>`: log an evaluation run
- `evals`: list recent evaluations
- `deployment_gate`: run deployment readiness gate
- `red_team <scenario>`: generate red-team risks + mitigations
- `mode <fast|rigorous>`: toggle analysis mode
- `edge_mode <offline|online|auto>`: force edge/offline or cloud routing
- `profile <name>`: set a profile tag for the assistant
- `models`: show model run summary (latency/tokens/cost)
- `feedback <rating> | <notes>`: log user feedback
- `team <task>`: run a simple multi-agent team (planner/builder/reviewer)
- `jobs`: list recent jobs
- `a2a <sender -> receiver | message>`: send agent-to-agent message
- `mcp <provider | json>`: call an MCP provider

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
MCP_GITHUB_URL=http://localhost:9000/github
MCP_DRIVE_URL=http://localhost:9000/drive
GITHUB_TOKEN=...
GOOGLE_DRIVE_TOKEN=...
OPENAI_COST_INPUT_PER_1M=0
OPENAI_COST_OUTPUT_PER_1M=0
OLLAMA_COST_INPUT_PER_1M=0
OLLAMA_COST_OUTPUT_PER_1M=0
```

## Endpoints
- `GET /health` => `ok`
- `GET /api/metrics` => JSON metrics
- `GET /api/trace` => recent events
- `GET /api/jobs` => recent jobs
- `GET /api/models` => model run summary
- `GET /api/a2a` => recent A2A messages
- `POST /api/command` => send a command

## Tests
```powershell
python -m unittest discover -s tests
python evals/run_evals.py
```
