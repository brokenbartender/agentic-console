from __future__ import annotations

import json
import os
import glob

DATA_DIR = os.getenv("AGENTIC_DATA_DIR", os.path.join(os.getcwd(), "data"))
RUNS_DIR = os.path.join(DATA_DIR, "runs")
OUT_PATH = os.path.join(DATA_DIR, "fine_tune.jsonl")

records = 0
with open(OUT_PATH, "w", encoding="utf-8") as out:
    for run_dir in sorted(glob.glob(os.path.join(RUNS_DIR, "*"))):
        summary = os.path.join(run_dir, "summary.md")
        if not os.path.exists(summary):
            continue
        try:
            with open(summary, "r", encoding="utf-8") as handle:
                text = handle.read()
            prompt = "Summarize the plan for this run:"
            completion = text.strip()
            out.write(json.dumps({"prompt": prompt, "completion": completion}) + "\n")
            records += 1
        except Exception:
            continue

print(f"Wrote {records} records to {OUT_PATH}")
