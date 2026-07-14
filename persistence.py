# ---------------------------------------------------------------------------
# Persistence — schema & mapping storage  (persistence.py)
# ---------------------------------------------------------------------------

"""
Single home for all pipeline persistence.

Owns the on-disk layout, the JSON round-trips (both directions), and the
raw-response debug records. The dataclasses in datamodels.py stay pure data
contracts.

All storage locations are configured ONCE, in the constants at the top of
this module. Tests that need a temp directory reassign the constant, e.g.:

    persistence.SCHEMAS_DIR = tmp_path / "schemas"

(every function reads the constant at call time, so reassignment works).

Layout (mirrors the data/ provider → consumer convention):

    schemas/
    ├── <providing_system>/
    │   └── <consuming_system>/
    │       └── <message_stem>.schema.json
    mappings/
    ├── <outbound_providing_system>/
    │   └── <outbound_consuming_system>/
    │       └── <outbound_stem>__from__<inbound_providing>__<inbound_stem>.mapping.json
    responses/
    └── <timestamp>_<label>.txt          # raw LLM output, debug/replay only

Design notes on the mapping store:
- A mapping is keyed by its (inbound, outbound) file pair and housed under
  the OUTBOUND file's location — lineage describes how an outbound message
  is derived, so it lives where it exits.
- Stored mappings reference their schemas (path + fingerprint), they do NOT
  embed them. A mapping depends on two schemas and can go stale two ways:
  load_mapping recomputes both fingerprints from the live FileSchemas the
  caller supplies and treats any mismatch as a cache miss, so mappings built
  from since-re-extracted schemas are never silently returned.

Supersedes the no-op persist_artifact / load_artifact stubs in config.py.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from datamodels import FieldMapping, FieldSchema, FileMapping, FileSchema, SampleFile

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Storage locations — the ONLY place directories are configured
# ---------------------------------------------------------------------------

_MODULE_DIR = Path(__file__).resolve().parent

SCHEMAS_DIR = _MODULE_DIR / "schemas"
MAPPINGS_DIR = _MODULE_DIR / "mappings"
RESPONSES_DIR = _MODULE_DIR / "responses"


# ---------------------------------------------------------------------------
# 1 · Schema store
# ---------------------------------------------------------------------------


def schema_path_for(sample: SampleFile) -> Path:
    """Where the stored schema for this sample lives (or would live).

    Path scheme: SCHEMAS_DIR/<providing_system>/<consuming_system or 'none'>/<stem>.schema.json
    """
    target_dir = SCHEMAS_DIR / sample.providing_system / (sample.consuming_system or "none")
    file_name = Path(sample.message_file_name).stem + ".schema.json"
    return target_dir / file_name


def schema_exists(sample: SampleFile) -> bool:
    """True if a schema for this sample has already been stored."""
    return schema_path_for(sample).is_file()


def store_schema(file_schema: FileSchema) -> Path:
    """Write one FileSchema to disk as JSON. Returns the path written."""
    target_path = schema_path_for(file_schema.source)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(schema_to_json(file_schema), encoding="utf-8")
    logger.info("Stored schema for %s at %s", file_schema.source.path, target_path)
    return target_path


def load_schema(sample: SampleFile) -> FileSchema | None:
    """Load a previously stored schema for this sample, if one exists.

    Returns None on a cache miss (or unreadable file) so callers can fall
    back to a fresh LLM extraction. The live SampleFile is reused as the
    source so raw_content and provenance are preserved — the stored JSON
    holds source metadata only, not raw content.
    """
    schema_path = schema_path_for(sample)
    if not schema_path.is_file():
        return None

    try:
        stored = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("Could not load stored schema %s: %s", schema_path, error)
        return None

    fields = [_field_from_dict(f) for f in stored.get("fields", [])]
    logger.info("Loaded cached schema for %s from %s", sample.path, schema_path)
    return FileSchema(source=sample, fields=fields)


# --- Schema JSON round-trip ------------------------------------------------
# Writer and reader live side by side so a change to one is visible from the
# other. If you add an attribute to _field_to_dict, add it to _field_from_dict.


def schema_to_json(file_schema: FileSchema) -> str:
    """Serialise a FileSchema (with provenance) to a JSON string."""
    schema_dict = {
        "source": _source_to_dict(file_schema.source),
        "fields": [_field_to_dict(f) for f in file_schema.fields],
    }
    return json.dumps(schema_dict, indent=2)


def _source_to_dict(sample: SampleFile) -> dict[str, Any]:
    """Provenance block used by both the schema and mapping stores."""
    return {
        "path": str(sample.path),
        "providing_system": sample.providing_system,
        "consuming_system": sample.consuming_system,
        "message_file_name": sample.message_file_name,
        "file_format": sample.file_format,
    }


def _field_to_dict(field: FieldSchema) -> dict[str, Any]:
    """Recursively convert one FieldSchema (and children) to a plain dict."""
    data: dict[str, Any] = {
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
        data["children"] = [_field_to_dict(child) for child in field.children]
    return data


def _field_from_dict(data: dict[str, Any]) -> FieldSchema:
    """Recursively rebuild one FieldSchema (and children) from a plain dict.

    Exact inverse of _field_to_dict — keys match FieldSchema attributes
    one-to-one, so a store → load round trip yields an equivalent schema.
    """
    return FieldSchema(
        name=data["name"],
        data_type=data["data_type"],
        nullable=data.get("nullable", False),
        description=data.get("description"),
        fmt=data.get("fmt"),
        enum_values=data.get("enum_values"),
        children=[_field_from_dict(child) for child in data.get("children", [])],
    )


# ---------------------------------------------------------------------------
# 2 · Mapping store
# ---------------------------------------------------------------------------


def _schema_fingerprint(file_schema: FileSchema) -> str:
    """Deterministic fingerprint of a schema's content, for staleness checks.

    Hashes the serialised JSON, so any change to fields (or provenance)
    after re-extraction produces a different fingerprint.
    """
    return hashlib.sha256(schema_to_json(file_schema).encode("utf-8")).hexdigest()[:16]


def mapping_path_for(inbound: SampleFile, outbound: SampleFile) -> Path:
    """Where the stored mapping for this (inbound, outbound) pair lives.

    Housed under the outbound file's provider/consumer directory; the
    filename records which inbound file it was derived from:

        MAPPINGS_DIR/<outbound_providing>/<outbound_consuming or 'none'>/
            <outbound_stem>__from__<inbound_providing>__<inbound_stem>.mapping.json
    """
    target_dir = MAPPINGS_DIR / outbound.providing_system / (outbound.consuming_system or "none")
    file_name = (
        Path(outbound.message_file_name).stem
        + "__from__"
        + inbound.providing_system
        + "__"
        + Path(inbound.message_file_name).stem
        + ".mapping.json"
    )
    return target_dir / file_name


def mapping_exists(inbound: SampleFile, outbound: SampleFile) -> bool:
    """True if a mapping for this (inbound, outbound) pair has been stored.

    Existence only — does NOT check staleness. Use load_mapping (which
    returns None for stale entries) when deciding whether to skip LLM work.
    """
    return mapping_path_for(inbound, outbound).is_file()


def store_mapping(mapping: FileMapping) -> Path:
    """Write one FileMapping to disk as JSON. Returns the path written.

    Schemas are stored as references (source provenance + fingerprint),
    never embedded — the schema store remains the single source of truth
    for field definitions.
    """
    target_path = mapping_path_for(mapping.inbound_source.source, mapping.outbound_source.source)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(mapping_to_json(mapping), encoding="utf-8")
    logger.info(
        "Stored mapping %s -> %s at %s",
        mapping.inbound_source.source.path,
        mapping.outbound_source.source.path,
        target_path,
    )
    return target_path


def load_mapping(inbound: FileSchema, outbound: FileSchema) -> FileMapping | None:
    """Load the stored mapping for this schema pair, if present AND current.

    Returns None on a miss, an unreadable file, or — critically — a stale
    entry: the fingerprints of the supplied live schemas are compared to the
    fingerprints recorded at store time, and any mismatch means one of the
    schemas has been re-extracted since the mapping was computed, so the
    caller should re-run the LLM mapping rather than trust the old result.

    The live FileSchemas are reused as inbound_source/outbound_source so
    provenance (including raw_content on their SampleFiles) is preserved.
    """
    mapping_path = mapping_path_for(inbound.source, outbound.source)
    if not mapping_path.is_file():
        return None

    try:
        stored = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("Could not load stored mapping %s: %s", mapping_path, error)
        return None

    # Staleness check — both parents must match what the mapping was built from.
    stored_in_fp = stored.get("inbound_schema", {}).get("fingerprint")
    stored_out_fp = stored.get("outbound_schema", {}).get("fingerprint")
    if stored_in_fp != _schema_fingerprint(inbound) or stored_out_fp != _schema_fingerprint(outbound):
        logger.info(
            "Stored mapping %s is stale (a source schema was re-extracted); ignoring",
            mapping_path,
        )
        return None

    field_mappings = [_field_mapping_from_dict(m) for m in stored.get("mappings", [])]
    logger.info("Loaded cached mapping from %s", mapping_path)
    return FileMapping(
        outbound_source=outbound,
        inbound_source=inbound,
        related=stored.get("related", False),
        relatedness_confidence=float(stored.get("relatedness_confidence", 0.0)),
        relatedness_reasoning=stored.get("relatedness_reasoning", ""),
        mappings=field_mappings,
    )


# --- Mapping JSON round-trip -------------------------------------------------
# Same discipline as the schema round-trip: writer and reader side by side.


def mapping_to_json(mapping: FileMapping) -> str:
    """Serialise a FileMapping to a JSON string, with schema references."""
    mapping_dict = {
        "inbound_schema": {
            "source": _source_to_dict(mapping.inbound_source.source),
            "schema_path": str(schema_path_for(mapping.inbound_source.source)),
            "fingerprint": _schema_fingerprint(mapping.inbound_source),
        },
        "outbound_schema": {
            "source": _source_to_dict(mapping.outbound_source.source),
            "schema_path": str(schema_path_for(mapping.outbound_source.source)),
            "fingerprint": _schema_fingerprint(mapping.outbound_source),
        },
        "related": mapping.related,
        "relatedness_confidence": mapping.relatedness_confidence,
        "relatedness_reasoning": mapping.relatedness_reasoning,
        "mappings": [_field_mapping_to_dict(m) for m in mapping.mappings],
    }
    return json.dumps(mapping_dict, indent=2)


def _field_mapping_to_dict(field_mapping: FieldMapping) -> dict[str, Any]:
    """Convert one FieldMapping to a plain dict (all attributes are primitives)."""
    return {
        "outbound_field": field_mapping.outbound_field,
        "sources": list(field_mapping.sources),
        "transformation": field_mapping.transformation,
        "confidence": field_mapping.confidence,
        "reasoning": field_mapping.reasoning,
    }


def _field_mapping_from_dict(data: dict[str, Any]) -> FieldMapping:
    """Rebuild one FieldMapping from a plain dict.

    Exact inverse of _field_mapping_to_dict. UNMAPPED is the safe default
    for a missing transformation so a partial record degrades honestly.
    """
    return FieldMapping(
        outbound_field=data.get("outbound_field", ""),
        sources=[str(s) for s in data.get("sources", [])],
        transformation=data.get("transformation", "UNMAPPED"),
        confidence=float(data.get("confidence", 0.0)),
        reasoning=data.get("reasoning", ""),
    )


# ---------------------------------------------------------------------------
# 3 · Raw LLM response records (debug / replay)
# ---------------------------------------------------------------------------


def record_raw_response(response: str, label: str = "response") -> None:
    """Fire-and-forget: dump raw LLM text to disk for debugging and replay.

    Written BEFORE any JSON parsing so failed extractions are captured too —
    those are the interesting ones. Timestamped so retries and re-runs never
    overwrite each other. Never raises: a failed debug write must not kill
    the pipeline. Nothing on the hot path reads these files.
    """
    try:
        RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        (RESPONSES_DIR / f"{stamp}_{label}.txt").write_text(response, encoding="utf-8")
    except OSError as error:
        logger.warning("Could not record raw LLM response: %s", error)