# Policy

Agentic Console uses a simple policy layer based on tool risk and autonomy level.

## Autonomy levels

- `supervised` requires confirmations for most actions.
- `semi` allows safe tools without confirmation.
- `autonomous` allows safe and caution tools without confirmation.

Set with `AGENTIC_AUTONOMY_LEVEL`.

## Tool risk

Tools can be tagged with risk levels. Destructive actions always require confirmation.

## Approvals

Step approval can be toggled in the UI or via the command `step_approval on|off`.

## Policy file

Set `AGENTIC_POLICY_PATH` to point to an external policy file when you need custom rules.
