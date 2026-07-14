
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


