
# ---------------------------------------------------------------------------
# Shared data models
# ---------------------------------------------------------------------------
 
from __future__ import annotations # delays evaluation to allow forward evaluation of FieldSchema

import os
from pathlib import Path
from typing import Literal, Any
from dataclasses import dataclass, field



@dataclass
class SampleFile:
    """A single source data sample plus the context it was found in."""
    # Ingestion produces these files
    
    path: Path
    parent_system: str # system sending file
    child_system: str | None  # system recieving file
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
    """Full extracted schema for one SampleFile, with provenance."""
 
    source: SampleFile
    fields: list[FieldSchema]

@dataclass
class DomainKnowledge:
    """Merged, alias-resolved catalogue of fields across all sources."""
 
    canonical_fields: dict[str, FieldSchema]
    provenance: dict[str, list[Path]]  # canonical field -> source files
    relationships: list[tuple[str, str]]  # cross-file shared keys

@dataclass
class Ontology:
    """Business concepts and their relationships."""
 
    entities: dict[str, list[str]]  # entity -> attribute names
    relationships: list[tuple[str, str, str]]  # (subject, predicate, object)
    field_to_concept: dict[str, str]  # canonical field -> "Entity.attribute"

@dataclass
class SemanticSchema:
    """Canonical cross-source schema derived from the ontology."""
 
    definition: dict[str, Any]
    source_mappings: dict[Path, dict[str, str]]  # source field -> canonical
