from __future__ import annotations

import os
from dataclasses import dataclass


def _load_dotenv() -> None:
    env_path = os.getenv("AGENTIC_ENV_FILE")
    if not env_path:
        env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip().lstrip("\ufeff")
                value = value.strip().strip("\"").strip("'")
                if key:
                    os.environ[key] = value
    except Exception:
        return


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


@dataclass
class Settings:
    data_dir: str = _env("AGENTIC_DATA_DIR", os.path.join(os.getcwd(), "data"))
    memory_db: str = _env("AGENTIC_MEMORY_DB", os.path.join(os.getcwd(), "data", "memory.db"))
    log_file: str = _env("AGENTIC_LOG_FILE", os.path.join(os.getcwd(), "data", "agentic.log"))
    ollama_base: str = _env("OLLAMA_BASE", "http://127.0.0.1:11434")
    ollama_model: str = _env("OLLAMA_MODEL", "phi3:latest")
    openai_model: str = _env("OPENAI_MODEL", "gpt-5.1")
    openai_reasoning_model: str = _env("OPENAI_REASONING_MODEL", _env("OPENAI_MODEL", "gpt-5.1"))
    openai_coding_model: str = _env("OPENAI_CODING_MODEL", _env("OPENAI_MODEL", "gpt-5.1"))
    ollama_reasoning_model: str = _env("OLLAMA_REASONING_MODEL", _env("OLLAMA_MODEL", "phi3:latest"))
    ollama_coding_model: str = _env("OLLAMA_CODING_MODEL", _env("OLLAMA_MODEL", "phi3:latest"))
    embedding_dim: int = int(_env("AGENTIC_EMBEDDING_DIM", "256"))
    short_memory_ttl: int = int(_env("AGENTIC_SHORT_MEMORY_TTL", "86400"))
    long_memory_ttl: int = int(_env("AGENTIC_LONG_MEMORY_TTL", "2592000"))
    max_chat_turns: int = int(_env("CHAT_HISTORY_TURNS", "20"))
    auto_summarize: str = _env("AGENTIC_AUTO_SUMMARIZE", "true")
    task_queue_size: int = int(_env("AGENTIC_TASK_QUEUE_SIZE", "100"))
    autonomy_level: str = _env("AGENTIC_AUTONOMY_LEVEL", "semi")
    server_host: str = _env("AGENTIC_WEB_HOST", "127.0.0.1")
    server_port: int = int(_env("AGENTIC_WEB_PORT", "8333"))


def get_settings() -> Settings:
    _load_dotenv()
    return Settings()
