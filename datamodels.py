
# ---------------------------------------------------------------------------
# Shared data models
# ---------------------------------------------------------------------------
 
from __future__ import annotations # delays evaluation to allow forward evaluation of FieldSchema

import os
import json
from pathlib import Path
from typing import Literal, Any
from dataclasses import dataclass, field


import logging
logger = logging.getLogger(__name__)

@dataclass
class SampleFile:
    """A single source data sample plus the context it was found in."""
    # Ingestion produces these files
    
    path: Path
    providing_system: str # system providing file
    consuming_system: str | None  # system consuming file
    message_file_name: str  # e.g. "loan_application_data"
    file_format: Literal["json", "csv", "xml", "avro", "txt"] # Need to cap and control this 
    raw_content: Any

@dataclass
class FieldSchema:
    """One field within an extracted schema."""
 
    name: str
    data_type: str
    nullable: bool
    description: str | None = None
    fmt: str | None = None  # e.g. "iso8601", "currency"
    enum_values: list[str] | None = None
    children: list[FieldSchema] = field(default_factory=list)  # nested objects

@dataclass
class FileSchema:
    """
    Full extracted schema for one SampleFile, with provenance.
    """

    source: SampleFile
    fields: list[FieldSchema]

    def flatten_fields_as_string(self) -> str:
        """Flatten this file's (possibly nested) fields into one line per field,
        suitable for dropping straight into an LLM prompt.

        Object children are joined with '.'; array children get '[]' appended
        to the array field's own path before the child name, e.g.:

            address.postcode: string
            previous_addresses[].postcode: string nullable
            previous_addresses[].history[].year: integer
        """

        lines: list[str] = []

        def _walk(field: FieldSchema, prefix: str | None) -> None:
            path = field.name if prefix is None else f"{prefix}.{field.name}"

            details = [field.data_type]
            if field.nullable:
                details.append("nullable")
            if field.fmt:
                details.append(f"format={field.fmt}")
            if field.enum_values:
                details.append(f"enum={field.enum_values}")
            line = f"{path}: {' '.join(details)}"
            if field.description:
                line += f" — {field.description}"
            lines.append(line)

            if field.children:
                child_prefix = f"{path}[]" if field.data_type == "array" else path
                for child in field.children:
                    _walk(child, child_prefix)

        for top_level_field in self.fields:
            _walk(top_level_field, None)

        return "\n".join(lines)
    
    def file_schema_as_json(self):
        """Convert FileSchema to nested JSON format."""

        def field_to_dict(field: FieldSchema) -> dict:
            data = {
                "name": field.name,
                "data_type": field.data_type,
                "nullable": field.nullable,
            }
            if field.description is not None:
                data["description"] = field.description
            if field.fmt is not None:
                data["fmt"] = field.fmt
            if field.enum_values is not None:
                data["enum_values"] = field.enum_values
            if field.children:
                data["children"] = [field_to_dict(child) for child in field.children]
            return data
        
        schema_dict = {
            "source": {
                "path": str(self.source.path),
                "providing_system": self.source.providing_system,
                "consuming_system": self.source.consuming_system,
                "message_file_name": self.source.message_file_name,
                "file_format": self.source.file_format,
            },
            "fields": [field_to_dict(f) for f in self.fields]
        }
        return json.dumps(schema_dict, indent=2)



