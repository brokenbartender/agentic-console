# Memory

Agentic Console stores memories in `data/memory.db` using an embedded SQLite store.

## Scopes and status

- Scopes: `shared` or `private`
- Status: `active`, `quarantined`, or `deprecated`

## TTL and pruning

- Short and long TTL values are configurable.
- Expired memories are pruned on read.

## CLI commands

```
python runtime\run.py memory show
python runtime\run.py memory search "query"
python runtime\run.py memory pin "important note"
python runtime\run.py memory clear
```

## Access control

Memories can include ACLs. If a memory has a user allowlist, only matching `user_id` can see it.
