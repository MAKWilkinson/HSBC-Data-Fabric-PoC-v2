
# ---------------------------------------------------------------------------
# 2 · Per-file schema extraction (LLM)  (extraction.py)
# ---------------------------------------------------------------------------


from __future__ import annotations

from pathlib import Path
from importlib import resources
from string import Template
from typing import Literal, Any
import json
import time

from datamodels import SampleFile, FieldSchema, FileSchema, FieldMapping, FileMapping
import config
import persistence

import logging
logger = logging.getLogger(__name__)


"""

Get LLM to determine Schema for files
Convert unstructured LLM output of schema extraction into FieldSchemas
prompt → Call → Normalise to FieldSchema  → Validate

"""

def retrieve_extracted_schema():
    pass


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


def normalise_schema(raw: dict[str, Any]) -> list[FieldSchema]:
    """Map raw LLM output into the canonical ``FieldSchema`` representation."""

    def normalise_field(field_data: dict[str, Any]) -> FieldSchema:
        """Recursively convert a raw field dict into a FieldSchema."""

        # Extract required fields with safe defaults.
        # str(... or "") guards against explicit nulls / non-string values
        # from the LLM — .get's default only applies when the key is absent.
        name = str(field_data.get("name") or "").strip()
        if not name:
            raise ValueError("Field must have a non-empty 'name'")

        data_type = str(
            field_data.get("data_type") or field_data.get("type") or "string"
        ).strip().lower()

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

        # Recursively process nested fields; a malformed child is skipped
        # rather than allowed to sink the whole schema.
        children = []
        nested_data = field_data.get("children") or field_data.get("nested_fields") or []
        if isinstance(nested_data, list):
            for child in nested_data:
                if not isinstance(child, dict):
                    continue
                try:
                    children.append(normalise_field(child))
                except (ValueError, AttributeError, TypeError) as error:
                    logger.warning(
                        "Skipping malformed nested field under %r: %s", name, error
                    )

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
            fields = []
            for field in raw["fields"]:
                if not isinstance(field, dict):
                    continue
                try:
                    fields.append(normalise_field(field))
                except (ValueError, AttributeError, TypeError) as error:
                    logger.warning("Skipping malformed field: %s", error)
            return fields

        # Case 2: Direct dict of field names -> field defs
        # {"customer_id": {"type": "string", ...}, ...}
        if all(isinstance(v, dict) for v in raw.values()):
            fields = []
            for field_name, field_def in raw.items():
                field_def = dict(field_def)  # shallow copy
                field_def["name"] = field_name
                try:
                    fields.append(normalise_field(field_def))
                except (ValueError, AttributeError, TypeError) as error:
                    logger.warning("Skipping malformed field %r: %s", field_name, error)
            return fields

    # If we get here, the structure was unexpected
    raise ValueError(
        f"Unable to parse raw schema output. Expected dict with 'fields' key or "
        f"dict of field definitions, got: {type(raw).__name__}"
    )


# TODO: skipped in workflow - will implement following completion of minimum viable product
def validate_extracted_schema(schema: list[FieldSchema], sample: SampleFile) -> bool:
    """Check extracted fields against the actual sample; flag hallucinations."""
    raise NotImplementedError


def extract_detailed_schema(client: Any, sample: SampleFile) -> FileSchema:
    """Orchestrate prompt → call → normalise → validate for one file."""
    cached = persistence.load_schema(sample)
    if cached is not None:
        return cached

    prompt = build_schema_extraction_prompt(sample)
    response = config.call_llm(client, prompt)
    normalised = normalise_schema(response)
    file = FileSchema(source=sample, fields=normalised)

    persistence.store_schema(file)
    return file


def extract_all_schemas(client: Any, samples: list[SampleFile]) -> list[FileSchema]:
    """Loop driver over goal 1; returns a schema per sample file."""

    result = []
    for item in samples:
        try:
            result.append(extract_detailed_schema(client, item))
        except Exception as e:
            logger.error(f"Failed to extract schema for {item.message_file_name}: {e}")
            continue
    return result


