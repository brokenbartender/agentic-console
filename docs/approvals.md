# Approvals

Approvals gate risky steps and tools before execution.

## Step approvals

Enable step approval in the UI or via command:

```
step_approval on
```

## Tool approvals

Some tools are tagged to always require confirmation. Desktop automation may also be gated with `AGENTIC_DESKTOP_APPROVAL`.

## Allowing tools

When step approvals are enabled, you can explicitly allow a tool by setting the memory key `allow_tool:<name>` to `true`.

## Recommendations

- Keep approvals enabled for destructive actions.
- Use allowlists to narrow tool access.
