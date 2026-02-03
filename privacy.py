from __future__ import annotations

import os
import re
from urllib.parse import urlparse


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_-]{20,}")


def _split_list(value: str) -> list[str]:
    if not value:
        return []
    parts = []
    for chunk in re.split(r"[,\n;]+", value):
        cleaned = chunk.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def parse_allowed_paths(value: str) -> list[str]:
    roots = []
    for item in _split_list(value):
        expanded = os.path.expandvars(os.path.expanduser(item))
        roots.append(os.path.abspath(expanded))
    return roots


def parse_allowed_domains(value: str) -> list[str]:
    return [d.lower() for d in _split_list(value)]


def is_path_allowed(path: str, allowed_roots: list[str]) -> bool:
    if not allowed_roots:
        return True
    if not path:
        return False
    full = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))
    for root in allowed_roots:
        try:
            common = os.path.commonpath([full, root])
        except ValueError:
            continue
        if common == root:
            return True
    return False


def is_domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for allowed in allowed_domains:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def redact_text(text: str) -> str:
    if not text:
        return text
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _OPENAI_KEY_RE.sub("[REDACTED_KEY]", redacted)
    return redacted
