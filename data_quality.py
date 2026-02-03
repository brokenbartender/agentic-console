from __future__ import annotations

import csv
import os
from typing import Dict, List, Tuple


def _infer_delimiter(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".tsv":
        return "\t"
    return ","


def profile_tabular(path: str, max_rows: int = 5000) -> str:
    if not os.path.exists(path):
        raise RuntimeError("data_profile requires an existing file")
    delimiter = _infer_delimiter(path)
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return "Empty file."
        cols = [h.strip() or f"col_{i+1}" for i, h in enumerate(header)]
        missing: Dict[str, int] = {c: 0 for c in cols}
        seen_rows = 0
        for row in reader:
            seen_rows += 1
            for i, col in enumerate(cols):
                value = row[i].strip() if i < len(row) else ""
                if value == "":
                    missing[col] += 1
            if seen_rows >= max_rows:
                break
        total = seen_rows
        delim_label = "TAB" if delimiter == "\t" else "COMMA"
        lines = [
            f"Rows scanned: {total}",
            f"Columns: {len(cols)}",
            f"Delimiter: {delim_label}",
        ]
        lines.append("Missingness (top 10):")
        ranked = sorted(missing.items(), key=lambda x: x[1], reverse=True)[:10]
        for col, count in ranked:
            pct = (count / total * 100) if total else 0.0
            lines.append(f"- {col}: {count} ({pct:.1f}%)")
        if total >= max_rows:
            lines.append(f"Note: scanned first {max_rows} rows.")
        return "\n".join(lines)
