
# ---------------------------------------------------------------------------
# 0 · Cross-cutting scaffolding  (config.py)
# ---------------------------------------------------------------------------
 

from __future__ import annotations

import logging
import os
import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import ollama

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _coerce(value: str, target: type) -> Any:
    """Coerce an env-var string into the type of its default value.
    
    Reusable by all LLM client providers for config loading.
    """
    if target is bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if target in (int, float):
        return target(value)
    return value

# ---------------------------------------------------------------------------
# LLM client abstraction
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMClient(Protocol):
    """Common interface for any LLM provider (Ollama, Anthropic, OpenAI, etc).
    
    Implementers must provide:
    - chat(model: str, messages: list, options: dict) -> ChatResponse
    
    where ChatResponse has a .message.content field (or is adapted to match).
    """

    def chat(
            self,
            prompt: str,
    ) -> Any:
        """LLM chat with all default settings inferred from config.
        
        Returns an object with a .message.content field (provider-agnostic).
        """
        ...

class OllamaLLMClient(LLMClient):
    """Implementation of LLMClient for Ollama.
    
    Owns its own defaults and environment variable mapping. Stores config
    so that model, temperature, and other defaults are applied automatically
    unless explicitly overridden per call.
    """
    
    # Ollama-specific defaults
    _DEFAULTS: dict[str, Any] = {
        # Client Params
        "ollama_host": "http://localhost:11434",
        "request_timeout": 180,

        # Message Response Params
        "model": "llama3:8b",
        "temperature": 0.0,  # deterministic output for structured/JSON tasks
        "role": "system",  # Default role for chat messages

        # Pipeline threshold for schema validation
        "confidence_threshold": 0.7,  
    }
    
    # Maps env var -> config key; type is inferred from default value
    _ENV_MAP: dict[str, str] = {
        # Client Params
        "OLLAMA_HOST": "ollama_host",
        "OLLAMA_TIMEOUT": "request_timeout",

        # Message Response Params
        "OLLAMA_MODEL": "model",
        "OLLAMA_TEMPERATURE": "temperature",
        "ROLE": "role",
        
        # Pipeline threshold for schema validation
        "CONFIDENCE_THRESHOLD": "confidence_threshold",
    }
    
    @classmethod
    def load_config(cls, path: Path | None = None) -> dict[str, Any]:
        """Load Ollama config from defaults, JSON file, and environment variables.
        
        Precedence (lowest to highest): built-in defaults, optional JSON file,
        environment variables.
        
        Args:
            path: Optional path to settings.json
        
        Returns:
            Config dict with ollama_host, model, request_timeout, temperature, etc.
        """
        # Start with defaults
        config = dict(cls._DEFAULTS)
        
        # Merge from JSON file if provided
        if path is not None:
            file_path = Path(path)
            if file_path.exists():
                config.update(json.loads(file_path.read_text(encoding="utf-8")))
            else:
                logger.warning("Config file %s not found; using defaults + env", file_path)
        
        # Override with environment variables
        for env_var, key in cls._ENV_MAP.items():
            raw = os.getenv(env_var)
            if raw is not None:
                config[key] = _coerce(raw, type(cls._DEFAULTS[key]))
        
        return config
    
    def __init__(self, config: dict[str, Any]):
        """Initialize Ollama client with config.
        
        Args:
            config: Config dict from load_config() with ollama_host, model, timeout, etc.
        """
        self._client = ollama.Client(
            host=config["ollama_host"],
            timeout=config.get("request_timeout"),
        )
        self._config = config

    def chat(self, prompt: str) -> str:
        """
        Uses all default configs - insert individual prompt and get single answer.
        
        Args:
            prompt: The prompt string to send to the LLM
            
        Returns:
            The LLM's response text
        """
        response = self._client.chat(
            model=self._config["model"],
            messages=[{"role": self._config["role"], "content": prompt}],
            options={"temperature": self._config["temperature"]},
        )
        return response.message.content

class AnthropicLLMClient(LLMClient):
    ...

class HSBCLLMClient(LLMClient):
    ...

def get_llm_client(provider: str = "ollama", config_path: Path | None = None) -> LLMClient:
    """Construct and return a configured LLM client.
    
    The factory loads provider-specific config from defaults, JSON file, and
    environment variables. Each provider owns its own defaults and env vars.
    
    Args:
        provider: Which LLM provider to use ("ollama", "anthropic", etc)
        config_path: Optional path to settings.json with predefined configs
    
    Returns:
        An LLMClient instance pre-configured.
    
    Example usage::
    
        # Load with defaults + env vars
        client = get_llm_client()
        response = client.chat(messages=[...])
        
        # Load from JSON config file
        client = get_llm_client(config_path=Path("settings.json"))
        
        # Override temperature for one call
        response = client.chat(messages=[...], options={"temperature": 0.7})

        
    """
    if provider == "ollama":
        config = OllamaLLMClient.load_config(config_path)
        return OllamaLLMClient(config)
    # elif provider == "anthropic":
    #      config = AnthropicLLMClient.load_config(config_path)
    #      return AnthropicLLMClient(config)
    # elif provider == "hsbc":
    #      config = HSBCLLMClient.load_config(config_path)
    #      return HSBCLLMClient(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}.")
 
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
 