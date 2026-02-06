# A2A Bridge Setup (Desktop + Work)

This enables two Agentic Console CLIs to exchange messages automatically once started.

## 1) Pull latest on BOTH machines
```powershell
cd C:\Users\codym\AgenticConsole
git pull
```

## 2) Add these to `.env` on BOTH machines
```
AGENTIC_A2A_LISTEN=true
AGENTIC_A2A_HOST=0.0.0.0
AGENTIC_A2A_PORT=9451
AGENTIC_A2A_SHARED_SECRET=change_me
AGENTIC_A2A_PEERS=desktop=100.111.161.110:9451,work=100.98.190.75:9451
```

## 3) Set node name per machine
**On work machine:**
```
AGENTIC_NODE_NAME=work
```

**On desktop:**
```
AGENTIC_NODE_NAME=desktop
```

## 4) Start the app on BOTH machines
```powershell
python app.py
```

## 5) Visual confirmation (desktop)
In the desktop UI log:
```
A2A network listening on http://0.0.0.0:9451/a2a
```

## Note (startup log guard)
If you recently updated and saw a crash during startup, ensure you are on the latest commit.
There was a fix to allow early A2A log messages before the UI log widget initializes.

## 6) Test messages (from work)
```
a2a_peers
a2a_send desktop hello-from-work
a2a_broadcast system-started
```

If the desktop is running, it will accept the message and store it in SQLite (`a2a_messages`).

## Troubleshooting
- If `a2a_peers` shows empty, re-check `AGENTIC_A2A_PEERS`.
- If connection fails, ensure firewall allows inbound TCP 9451 on both machines.
- Ensure both are on Tailscale and the IPs match.
