
# ---------------------------------------------------------------------------
# 0 · Cross-cutting scaffolding  (config.py)
# ---------------------------------------------------------------------------
 

from __future__ import annotations


import os
import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import json
import time

import ollama
import boto3

from datamodels import SampleFile, FieldSchema, FileSchema, FieldMapping, FileMapping
import config
import persistence

import logging
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def call_llm(
    client: Any, 
    prompt: str = "", 
    max_attempts: int = 1, 
    backoff_base_seconds: float = 2.0,
) -> dict[str, Any]:

    """Single LLM call returning raw structured schema output (with retries)."""
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            # === SDK swap point ===
            # Assumes the injected client exposes `complete(prompt) -> str`.
            # Once the SDK is chosen, change only this line (and the import).
            response: str = client.chat(prompt)
            persistence.record_raw_response(response, label="response")
            return config.extract_json(response)
        
        except Exception as error:  # noqa: BLE001 - SDK undecided; retry broadly
            last_error = error
            logger.warning(
                "schema extraction attempt %d/%d failed: %s",
                attempt,
                max_attempts,
                error,
            )
            if attempt < max_attempts:
                time.sleep(backoff_base_seconds * 2 ** (attempt - 1))
    assert last_error is not None
    raise last_error

def extract_json(text: str) -> dict[str, Any]:
    """Parse a JSON object from raw LLM text, tolerating code fences/prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop the opening fence (``` or ```json) and the closing fence.
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[len("json") :]
        cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the outermost { ... } span if the model added prose.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


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
        "request_timeout": 600,

        # Message Response Params
        "model": "llama3:8b",
        "temperature": 0.0,  # deterministic output for structured/JSON tasks
        "role": "system",  # Default role for chat messages
        "format": "json", # Forces chat responses to conform to json

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
        "FORMAT": "format",
        
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
            format=self._config["format"]
        )
        return response.message.content


class AnthropicLLMClient(LLMClient):
    ...




class BedrockLLMClient(LLMClient):
    """Implementation of LLMClient for AWS Bedrock (Anthropic Claude models).

    Auth: boto3 automatically uses the AWS_BEARER_TOKEN_BEDROCK env var
    (Bedrock API key) if set, otherwise falls back to the standard AWS
    credential chain (env vars, ~/.aws, instance role).
    """

    _DEFAULTS: dict[str, Any] = {
        # Client Params
        "aws_region": "eu-west-2",
        "request_timeout": 600,

        "model": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "temperature": 0.0,
        "max_tokens": 8192,

        # Pipeline threshold for schema validation
        "confidence_threshold": 0.7,
    }

    _ENV_MAP: dict[str, str] = {
        "AWS_REGION": "aws_region",
        "BEDROCK_TIMEOUT": "request_timeout",
        "BEDROCK_MODEL": "model",
        "BEDROCK_TEMPERATURE": "temperature",
        "BEDROCK_MAX_TOKENS": "max_tokens",
        "CONFIDENCE_THRESHOLD": "confidence_threshold",
    }

    @classmethod
    def load_config(cls, path: Path | None = None) -> dict[str, Any]:
        """Same precedence as OllamaLLMClient: defaults < JSON file < env vars."""
        config = dict(cls._DEFAULTS)

        if path is not None:
            file_path = Path(path)
            if file_path.exists():
                config.update(json.loads(file_path.read_text(encoding="utf-8")))
            else:
                logger.warning("Config file %s not found; using defaults + env", file_path)

        for env_var, key in cls._ENV_MAP.items():
            raw = os.getenv(env_var)
            if raw is not None:
                config[key] = _coerce(raw, type(cls._DEFAULTS[key]))

        return config

    def __init__(self, config: dict[str, Any]):
        from botocore.config import Config as BotoConfig

        self._client = boto3.client(
            "bedrock-runtime",
            region_name=config["aws_region"],
            config=BotoConfig(
                read_timeout=config.get("request_timeout"),
                connect_timeout=30,
                retries={"max_attempts": 0},  # call_llm owns retry policy
            ),
        )
        self._config = config

    def chat(self, prompt: str) -> str:
            """Single prompt in, response text out — same contract as Ollama's chat."""
            logger.info(
                "Bedrock request: model=%s region=%s prompt_chars=%d",
                self._config["model"], self._config["aws_region"], len(prompt),
            )

            response = self._client.converse(
                modelId=self._config["model"],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "temperature": self._config["temperature"],
                    "maxTokens": self._config["max_tokens"],
                },
            )

            stop_reason = response.get("stopReason", "")
            usage = response.get("usage", {})
            logger.info(
                "Bedrock response: stopReason=%s inputTokens=%s outputTokens=%s",
                stop_reason, usage.get("inputTokens"), usage.get("outputTokens"),
            )

            # Fable 5 can decline requests: the API returns HTTP 200 with a
            # refusal stop reason rather than an error. Raise so call_llm's
            # retry/error path handles it instead of extract_json choking.
            if stop_reason == "refusal":
                raise RuntimeError(f"Model refused the request (stopReason={stop_reason})")

            blocks = response["output"]["message"]["content"]
            text = "".join(b["text"] for b in blocks if "text" in b)

            if not text:
                raise RuntimeError(
                    f"Bedrock returned no text content "
                    f"(stopReason={stop_reason!r}, blocks={[list(b.keys()) for b in blocks]})"
                )

            return text

    
class HSBCLLMClient(LLMClient):
    ...


def get_llm_client(provider: str = "bedrock", config_path: Path | None = None) -> LLMClient:
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
    elif provider == "anthropic":
        config = AnthropicLLMClient.load_config(config_path)
        return AnthropicLLMClient(config)
    elif provider == "bedrock":
        config = BedrockLLMClient.load_config(config_path)
        return BedrockLLMClient(config)
    elif provider == "hsbc":
        config = HSBCLLMClient.load_config(config_path)
        return HSBCLLMClient(config)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}.")
 
 