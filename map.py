

from pathlib import Path
from string import Template
from typing import Any

from datamodels import SampleFile, FieldSchema, FileSchema, FieldMapping, FileMapping
import config
import persistence


import logging
logger = logging.getLogger(__name__)


"""
Issue with function - will run in n^2 comparing each FileSchema with FileSchema, making API call for each

Can reduce LLM API calls by starting with the following process
-> Check providing system and consuming system
-> Check consuming systems outbound messages
-> Only call LLM on the outbound messages

FOR POC - Call API in O(n^2), filtered on inbound.consuming == outbound.providing.
Caching via persistence.load_mapping / store_mapping avoids re-calling the LLM
for pairs whose schemas haven't changed since the mapping was stored.
"""


# Transformations the FieldMapping dataclass allows; anything else from the
# LLM degrades to UNMAPPED rather than propagating an invalid literal.
_VALID_TRANSFORMATIONS = {"EXACT", "RENAMED", "SEMANTIC", "MERGE", "TRANSFORMED", "UNMAPPED"}


def _build_mapping_prompt(inbound: FileSchema, outbound: FileSchema) -> str:
    """Assemble the field-mapping prompt for one inbound/outbound FileSchema pair.

    Follows the same load-template-and-substitute pattern as
    extraction.build_schema_extraction_prompt.
    """
    prompt_path = Path(__file__).parent / "prompts" / "file_mapping.md"
    template_text = prompt_path.read_text(encoding="utf-8")

    return Template(template_text).substitute(

        # inbound is the file sent from System A > System B
        inbound_providing_system=inbound.source.providing_system,
        inbound_consuming_system=inbound.source.consuming_system or "none",
        inbound_message_file_name=inbound.source.message_file_name,
        inbound_file_format=inbound.source.file_format,

        # outbound is the file sent from System B > System C
        outbound_providing_system=outbound.source.providing_system,
        outbound_consuming_system=outbound.source.consuming_system or "none",
        outbound_message_file_name=outbound.source.message_file_name,
        outbound_file_format=outbound.source.file_format,

        inbound_fields=inbound.flatten_fields_as_string(),
        outbound_fields=outbound.flatten_fields_as_string(),
    )


def normalise_field_mapping(raw_field: dict[str, Any]) -> FieldMapping:
    """Convert one raw LLM field-mapping dict into a FieldMapping.

    Tolerant of key variants the same way extraction.normalise_schema is:
    - outbound_field | target | target_field | outbound
    - sources | source | source_fields | inbound_fields (str or list)
    - transformation | transform | mapping_type (uppercased, validated)
    """
    outbound_field = str(
        raw_field.get("outbound_field")
        or raw_field.get("target_field")
        or raw_field.get("target")
        or raw_field.get("outbound")
        or ""
    ).strip()
    if not outbound_field:
        raise ValueError("Field mapping must have a non-empty 'outbound_field'")

    sources = (
        raw_field.get("sources")
        or raw_field.get("source_fields")
        or raw_field.get("source")
        or raw_field.get("inbound_fields")
        or []
    )
    # LLM may return a single string for a 1-to-1 mapping
    if isinstance(sources, str):
        sources = [sources]
    sources = [str(s).strip() for s in sources if s is not None and str(s).strip()]

    transformation = str(
        raw_field.get("transformation")
        or raw_field.get("transform")
        or raw_field.get("mapping_type")
        or "UNMAPPED"
    ).strip().upper()
    if transformation not in _VALID_TRANSFORMATIONS:
        logger.warning(
            "Unknown transformation %r for field %r; defaulting to UNMAPPED",
            transformation,
            outbound_field,
        )
        transformation = "UNMAPPED"

    # A field with no sources cannot be anything other than UNMAPPED
    if not sources:
        transformation = "UNMAPPED"

    try:
        confidence = float(raw_field.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))  # clamp to 0-1

    reasoning = str(raw_field.get("reasoning") or raw_field.get("reason") or "").strip()

    return FieldMapping(
        outbound_field=outbound_field,
        sources=sources,
        transformation=transformation,
        confidence=confidence,
        reasoning=reasoning,
    )


def normalise_mapping(
    raw: dict[str, Any],
    inbound: FileSchema,
    outbound: FileSchema,
) -> FileMapping:
    """Map raw LLM mapping output into the canonical FileMapping representation.

    Expected raw shape (tolerant of variants):
        {
            "related": bool,
            "relatedness_confidence": float,
            "relatedness_reasoning": str,
            "mappings": [ {outbound_field, sources, transformation, confidence, reasoning}, ... ]
        }
    """
    related = raw.get("related", raw.get("files_related", False))
    if not isinstance(related, bool):
        related = str(related).strip().lower() in ("true", "1", "yes")

    try:
        relatedness_confidence = float(
            raw.get("relatedness_confidence", raw.get("confidence", 0.0))
        )
    except (TypeError, ValueError):
        relatedness_confidence = 0.0
    relatedness_confidence = max(0.0, min(1.0, relatedness_confidence))

    relatedness_reasoning = str(
        raw.get("relatedness_reasoning") or raw.get("reasoning") or ""
    ).strip()

    raw_mappings = (
        raw.get("mappings")
        or raw.get("field_mappings")
        or raw.get("fields")
        or []
    )
    field_mappings: list[FieldMapping] = []
    if isinstance(raw_mappings, list):
        for raw_field in raw_mappings:
            if not isinstance(raw_field, dict):
                continue
            try:
                field_mappings.append(normalise_field_mapping(raw_field))
            except ValueError as error:
                logger.warning("Skipping malformed field mapping: %s", error)

    return FileMapping(
        outbound_source=outbound,
        inbound_source=inbound,
        related=related,
        relatedness_confidence=relatedness_confidence,
        relatedness_reasoning=relatedness_reasoning,
        mappings=field_mappings,
    )


def map_1f_a2a(client: Any, inbound: FileSchema, outbound: FileSchema) -> FileMapping:
    """Map one outbound FileSchema's fields back to one inbound FileSchema's fields.

    Single LLM call per (inbound, outbound) pair:
    prompt → call → normalise → FileMapping.
    Reuses extraction's call/parse machinery (prompt → call → JSON) rather
    than duplicating it.
    """
    prompt = _build_mapping_prompt(inbound, outbound)
    raw_mapping = config.call_llm(client, prompt)
    return normalise_mapping(raw_mapping, inbound=inbound, outbound=outbound)


def map_f2f(client: Any, files: list[FileSchema], use_cache: bool = True) -> list[FileMapping]:
    """Map every eligible (inbound, outbound) pair to a FileMapping.

    POC: naive N^2 — every file treated as a candidate outbound file mapped
    against every other file treated as a candidate inbound source. Only maps
    pairs where the inbound consuming system matches the outbound providing
    system.

    When use_cache is True, a stored non-stale mapping (persistence.load_mapping)
    is returned instead of re-calling the LLM, and fresh results are stored.
    """
    results: list[FileMapping] = []
    for outbound in files:
        for inbound in files:
            if inbound.source.consuming_system != outbound.source.providing_system:
                continue

            if use_cache:
                cached = persistence.load_mapping(inbound, outbound)
                if cached is not None:
                    results.append(cached)
                    continue

            mapping = map_1f_a2a(client, inbound, outbound)

            if use_cache:
                persistence.store_mapping(mapping)

            results.append(mapping)

    return results