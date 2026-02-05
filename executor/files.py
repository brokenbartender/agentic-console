"""
Centralized file operations for Agentic-Console.
Phase 2: all file mutations should route through here.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Tuple


def copy_path(src: str, dst: str) -> None:
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    if not os.path.exists(dst):
        raise RuntimeError("copy verification failed")


def move_path(src: str, dst: str) -> None:
    shutil.move(src, dst)
    if not os.path.exists(dst):
        raise RuntimeError("move verification failed")


def delete_to_trash(path: str, trash_dir: str) -> Tuple[str, str]:
    os.makedirs(trash_dir, exist_ok=True)
    base = os.path.basename(path.rstrip("\\/"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(trash_dir, f"{stamp}-{base}")
    shutil.move(path, target)
    return path, target


def mkdir_path(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def open_path(path: str) -> None:
    os.startfile(path)


def restore_path(src: str, dst: str) -> None:
    shutil.move(src, dst)
    if not os.path.exists(dst):
        raise RuntimeError("restore verification failed")
