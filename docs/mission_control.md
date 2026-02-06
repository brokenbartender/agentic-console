# Mission Control (Chainlit + Langfuse)

## Chainlit UI
Run:
```
pip install chainlit
chainlit run chainlit_app.py -w
```

This provides a chat UI with step visualization and A2A stream.

## Langfuse (Optional)
Set:
```
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Trace events will be emitted for task_event logs.
