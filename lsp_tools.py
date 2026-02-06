from __future__ import annotations

import ast
import os
from typing import List, Dict


def _py_files(root: str) -> List[str]:
    out = []
    for base, _, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.join(base, f))
    return out


def find_symbol_def(root: str, name: str) -> List[Dict[str, str]]:
    results = []
    for path in _py_files(root):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                    results.append({"path": path, "line": str(node.lineno), "kind": type(node).__name__})
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id == name:
                            results.append({"path": path, "line": str(node.lineno), "kind": "Assign"})
        except Exception:
            continue
    return results


def find_inherits(root: str, base_name: str) -> List[Dict[str, str]]:
    results = []
    for path in _py_files(root):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for b in node.bases:
                        if isinstance(b, ast.Name) and b.id == base_name:
                            results.append({"path": path, "line": str(node.lineno), "class": node.name})
        except Exception:
            continue
    return results
