# Data Constitution

These rules apply before data enters the agent pipeline.

## Required
- Reject empty documents.
- Reject documents shorter than 200 characters.

## Block Patterns
BLOCK: (?i)\bpassword\b
BLOCK: (?i)\bsecret\b
BLOCK: (?i)\bapi[_-]?key\b
BLOCK: (?i)\bprivate key\b
