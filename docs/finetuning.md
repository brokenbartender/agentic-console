# Fine-Tuning Hooks

This project does not include model fine-tuning, but supports a hook to run a
local adapter training pipeline. Recommended flow:
1) Curate a dataset (JSONL) with prompt/response pairs.
2) Train a LoRA adapter for a local model (e.g., Qwen or Llama).
3) Load the adapter in your local inference runtime.

This file documents the intended pipeline until a training script is added.
