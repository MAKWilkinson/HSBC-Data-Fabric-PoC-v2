
# ---------------------------------------------------------------------------
# 2 · Per-file schema extraction (LLM)  (extraction.py)
# ---------------------------------------------------------------------------


from __future__ import annotations

from pathlib import Path
from importlib import resources
from string import Template
from typing import Literal, Any
from datamodels import SampleFile, FieldSchema, FileSchema
import json
import time


import logging
logger = logging.getLogger(__name__)


"""

Get LLM to determine Schema for files
Convert unstructured LLM output of schema extraction into FieldSchemas
prompt → Call → Normalise to FieldSchema  → Validate

"""

def _extract_json(text: str) -> dict[str, Any]:
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


def build_schema_extraction_prompt(sample: SampleFile) -> str:
    """Assemble the extraction prompt, injecting department/interaction context."""
    prompt_path = Path(__file__).parent / "prompts" / "field_extraction.md"
    template_text = prompt_path.read_text(encoding="utf-8")

    return Template(template_text).substitute(
        providing_system=sample.providing_system,
        consuming_system=sample.consuming_system or "none",
        message_file_name=sample.message_file_name,
        file_format=sample.file_format,
        raw_content=sample.raw_content,
    )


def call_llm_extract_schema(
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
            return _extract_json(response)
        
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


def normalise_schema(raw: dict[str, Any]) -> list[FieldSchema]:
    """Map raw LLM output into the canonical ``FieldSchema`` representation."""
    
    def normalise_field(field_data: dict[str, Any]) -> FieldSchema:
        """Recursively convert a raw field dict into a FieldSchema."""
        
        # Extract required fields with safe defaults
        name = field_data.get("name", "").strip()
        if not name:
            raise ValueError("Field must have a non-empty 'name'")
        
        # TODO - data type not correctly mapping, all coming out of the llm as repsonse but not converting to type
        data_type = (field_data.get("data_type") or field_data.get("type", "string")).strip().lower()
        
        # Normalize common type variations
        type_map = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "dict": "object",
            "list": "array",
            "null": "null",
        }
        
        if data_type in type_map:
            data_type = type_map[data_type]
        
        nullable = field_data.get("nullable", False)
        if not isinstance(nullable, bool):
            nullable = str(nullable).lower() in ("true", "1", "yes")
        
        # Extract optional fields
        description = field_data.get("description")
        if description:
            description = str(description).strip()
        
        fmt = field_data.get("fmt") or field_data.get("format")
        if fmt:
            fmt = str(fmt).strip().lower()
        
        enum_values = field_data.get("enum_values") or field_data.get("enums")
        if enum_values and isinstance(enum_values, (list, tuple)):
            enum_values = [str(v).strip() for v in enum_values if v is not None]
        else:
            enum_values = None
        
        # Recursively process nested fields
        children = []
        nested_data = field_data.get("children") or field_data.get("nested_fields") or []
        if isinstance(nested_data, list):
            children = [normalise_field(child) for child in nested_data if isinstance(child, dict)]
        
        return FieldSchema(
            name=name,
            data_type=data_type,
            nullable=nullable,
            description=description,
            fmt=fmt,
            enum_values=enum_values,
            children=children,
        )
    
    # Handle different raw output structures
    if isinstance(raw, dict):
        # Case 1: {"fields": [...]} — most common LLM output structure
        if "fields" in raw and isinstance(raw["fields"], list):
            return [normalise_field(field) for field in raw["fields"] if isinstance(field, dict)]
        
        # Case 2: Direct dict of field names -> field defs
        # {"customer_id": {"type": "string", ...}, ...}
        if all(isinstance(v, dict) for v in raw.values()):
            fields = []
            for field_name, field_def in raw.items():
                field_def = dict(field_def)  # shallow copy
                field_def["name"] = field_name
                fields.append(normalise_field(field_def))
            return fields
    
    # If we get here, the structure was unexpected
    raise ValueError(
        f"Unable to parse raw schema output. Expected dict with 'fields' key or "
        f"dict of field definitions, got: {type(raw).__name__}"
    )


# TODO: skipped in pipeline - will implement following completion of minimum viable product
def validate_extracted_schema(schema: list[FieldSchema], sample: SampleFile) -> bool:
    """Check extracted fields against the actual sample; flag hallucinations."""
    raise NotImplementedError


def extract_detailed_schema(client: Any, sample: SampleFile) -> FileSchema:
    """Orchestrate prompt → call → normalise → validate for one file."""

    prompt = build_schema_extraction_prompt(sample)
    response = call_llm_extract_schema(client, prompt)
    normalised = normalise_schema(response)
    validated = normalised # line for when validation implemented, will need branching for not validated

    file = FileSchema(source=sample, fields=validated)
    
    return file


def extract_all_schemas(client: Any, samples: list[SampleFile]) -> list[FileSchema]:
    """Loop driver over goal 1; returns a schema per sample file."""

    result = []
    for item in samples:
        result.append(extract_detailed_schema(client, item))
    return result

