from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Dict


def index_repo_functions(repo_path: str) -> List[Dict[str, str]]:
    root = Path(repo_path)
    if not root.exists():
        raise RuntimeError("Repo path does not exist")
    results: List[Dict[str, str]] = []
    for path in root.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node) or ""
                results.append(
                    {
                        "file": str(path),
                        "function": node.name,
                        "doc": doc,
                    }
                )
    return results


def write_r2e_index(repo_path: str, out_path: str) -> str:
    entries = index_repo_functions(repo_path)
    lines = []
    for e in entries:
        lines.append(f"{e['file']}\t{e['function']}\t{e['doc']}")
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return out_path
