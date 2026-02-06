# A2A Auto-Reply Bridge

This script auto-responds to inbound A2A messages by running `codex exec` and sending a reply to the configured peer.

## Files
- `scripts/a2a_bridge.ps1`: polls `/api/a2a`, responds to peer messages, logs to `data/a2a_bridge.log`.
- `scripts/a2a_relay.ps1`: tails the log and prints inbound messages (optional).

## Environment
Ensure `.env` includes:
```
AGENTIC_A2A_LISTEN=true
AGENTIC_A2A_HOST=0.0.0.0
AGENTIC_A2A_PORT=9451
AGENTIC_A2A_SHARED_SECRET=your_secret
AGENTIC_NODE_NAME=laptop
AGENTIC_A2A_PEERS=desktop=100.x.x.x:9451,laptop=100.x.x.x:9451
```

## Run
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\a2a_bridge.ps1
```

Optional relay (echo inbound to console):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\a2a_relay.ps1
```

## Parameters
- `-PeerName` (default `desktop`)
- `-SenderName` (default from `AGENTIC_NODE_NAME`)
- `-SharedSecret` (default from `AGENTIC_A2A_SHARED_SECRET`)
- `-A2ASend` (derived from `AGENTIC_A2A_PEERS` if not set)

## Logs
`data/a2a_bridge.log` contains inbound/outbound messages for auditing.

## Memory
Inbound A2A messages are also persisted to the Agentic Console memory store
(kind=`a2a`, tags include sender/receiver), enabling self-improvement workflows.

Additionally, a compact per-thread summary is maintained in
`data/a2a_thread_summaries.json` and periodically persisted to memory
as `kind=a2a_thread_summary` with a 7-day TTL.
## UI Control
The Agentic Console UI includes an **A2A Control** tab with Start/Stop/Pause/Resume
and a live transcript. Using **Send & Join** pauses auto-reply so you can
participate in a 3-way conversation.

## Pause File
Auto-reply can be paused by writing:
`data/a2a_bridge_pause.json` => `{ "paused": true }`.
The UI controls this automatically.

## Agent Mode (A2A Router)
You can enable autonomous routing for inbound A2A messages using:
```
AGENTIC_A2A_AUTO_REPLY=true
AGENTIC_A2A_AGENT_MODE=plan   # off|chat|plan|auto
AGENTIC_A2A_EXECUTE=false
```

Message formats supported:
- Plain text → handled per mode
- `plan: <task>` or `task: <task>` → returns a plan
- JSON: `{"type":"plan","text":"<task>"}` or `{"type":"chat","text":"<message>"}`  
## Auto-Update
To keep the desktop/laptop in sync without manual pulls, use:

```
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\auto_update.ps1
```

This script pulls these repos by default:
- `C:\Users\codym\AgenticConsole`
- `C:\Users\codym\agentic-control-plane`
- `C:\Users\codym\codex-control-stack`

If AgenticConsole changes, it restarts the app and triggers A2A tasks.
Logs: `C:\Users\codym\AgenticConsole\data\auto_update.log`
