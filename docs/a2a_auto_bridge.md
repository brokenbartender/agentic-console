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
