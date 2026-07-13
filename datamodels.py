
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
    """
    A single source data sample plus the context it was found in.
    Output of ingestion process - turns all files in Data folder into SampleFiles
    """
    
    path: Path
    providing_system: str # system providing file
    consuming_system: str | None  # system consuming file
    message_file_name: str  # e.g. "loan_application_data"
    file_format: Literal["json", "csv", "xml", "avro", "txt"] # Need to cap and control this 
    raw_content: Any


@dataclass
class FieldSchema:
    """
    One field within an extracted schema.
    """
 
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


    def _schema_path(self, base_dir: Path | None = None) -> Path:
        """Compute where this schema would be stored, without writing anything."""
        if base_dir is None:
            base_dir = Path(__file__).resolve().parent / "schemas"
        target_dir = base_dir / self.source.providing_system / (self.source.consuming_system or "none")
        file_name = Path(self.source.message_file_name).stem + ".schema.json"
        return target_dir / file_name


    def schema_exists(self, base_dir: Path | None = None) -> bool:
        """True if a schema for this file has already been stored."""
        return self._schema_path(base_dir).is_file()


    def store_file_schema(self, base_dir: Path | None = None) -> Path:
        target_path = self._schema_path(base_dir)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(self.file_schema_as_json(), encoding="utf-8")
        logger.info("Stored schema for %s at %s", self.source.path, target_path)
        return target_path


@dataclass
class FieldMapping:
    """
    Fields mapped within a FileMapping, can be Optional Many to 1 
    i.e. many sources can feed 1 outbound field

    """
    outbound_field: str # outbound field exiting system
    sources: list[str] #list of FieldSchema's that are used to derive the outbound field
    transformation: Literal["EXACT", "RENAMED", "SEMANTIC", "MERGE", "TRANSFORMED", "UNMAPPED"]
    confidence: float # score 0-1 to determine how related
    reasoning: str


@dataclass
class FileMapping:
    """
    Mapping of 2 files 
    """
    outbound_source: FileSchema
    inbound_source: FileSchema
    related: bool # are the files related
    relatedness_confidence: float # score 0-1 to determine how related
    relatedness_reasoning: str # description of how the files appear to be related
    mappings: list[FieldMapping] 



