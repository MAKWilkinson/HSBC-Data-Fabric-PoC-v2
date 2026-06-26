
# ---------------------------------------------------------------------------
# 0 · Cross-cutting scaffolding  (config.py)
# ---------------------------------------------------------------------------
 

from __future__ import annotations

import logging
import os
import json
from pathlib import Path
from typing import Any
 
import ollama
 
logger = logging.getLogger(__name__)
 
# ---------------------------------------------------------------------------
# Defaults — every one overridable via env var
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, Any] = {
    "ollama_host": "http://localhost:11434",
    "model": "llama3:8b",
    "request_timeout": 180,
    "temperature": 0.0,  # deterministic output for structured/JSON tasks
    "confidence_threshold": 0.7,
    "role":"system",
}
 
# Maps env var -> config key; the default's type is used for coercion.
_ENV_MAP: dict[str, str] = {
    "OLLAMA_HOST": "ollama_host",
    "OLLAMA_MODEL": "model",
    "OLLAMA_TIMEOUT": "request_timeout",
    "OLLAMA_TEMPERATURE": "temperature",
    "CONFIDENCE_THRESHOLD": "confidence_threshold",
    "ROLE" : "role",
}
 
 
# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load pipeline config (model name, host, thresholds).
    can pass in settings.json
 
    Precedence (lowest to highest): built-in defaults, optional JSON file,
    environment variables.
    """

    # set config to copy of defaults
    config = dict(_DEFAULTS)
 
    # Reads from settings.json - if none provided uses defaults
    if path is not None:
        file_path = Path(path)
        if file_path.exists():
            config.update(json.loads(file_path.read_text(encoding="utf-8")))
        else:
            logger.warning("Config file %s not found; using defaults + env", file_path)
    
    # Reads from env variables and sets config to env variables if available 
    for env_var, key in _ENV_MAP.items():
        raw = os.getenv(env_var)
        if raw is not None:
            config[key] = _coerce(raw, type(_DEFAULTS[key]))
 
    return config
 
def _coerce(value: str, target: type) -> Any:
    """Coerce an env-var string into the type of its default value."""
    if target is bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if target in (int, float):
        return target(value)
    return value
 
# ---------------------------------------------------------------------------
# LLM client — implemented
# ---------------------------------------------------------------------------

def get_llm_client(config: dict[str, Any]) -> ollama.Client:
    """Construct and return a configured Ollama client.
 
    Build once and pass it down the pipeline. Model name and call options
    (``temperature``, ``format=...`` for JSON) live in ``config`` and are
    applied at each ``client.chat(...)`` call site, e.g.::
 
        client.chat(
            model=config["model"],
            messages=[...],
            format=MySchema.model_json_schema(),
            options={"temperature": config["temperature"]},
        )
    """
    return ollama.Client(
        host=config["ollama_host"],
        timeout=config.get("request_timeout", 120),
    )
 
 
# ---------------------------------------------------------------------------
# Caching — no-op stubs (disabled for the PoC)
# ---------------------------------------------------------------------------

def cache_key(*parts: str) -> str:
    """Stub: caching disabled. Returns a placeholder key (never looked up)."""
    return ""
 
 
def get_cached(key: str) -> Any | None:
    """Stub: caching disabled. Always reports a miss so the model is called."""
    return None
 
 
def cache_response(key: str, value: Any) -> None:
    """Stub: caching disabled. Silently discards the value."""
    return None
 
 
# ---------------------------------------------------------------------------
# Artifact checkpointing — no-op stubs (disabled for the PoC)
# ---------------------------------------------------------------------------

def persist_artifact(obj: Any, name: str) -> Path:
    """Stub: checkpointing disabled. Returns a nominal path without writing."""
    return Path(name)
 
 
def load_artifact(name: str) -> Any:
    """Stub: checkpointing disabled. Nothing was saved, so always raises."""
    raise FileNotFoundError(f"Checkpointing disabled — no artifact named {name!r}")
 