

from pathlib import Path
from string import Template
from typing import Literal, Any

from datamodels import SampleFile, FieldSchema, FileSchema, FieldMapping, FileMapping
import extraction

import logging
logger = logging.getLogger(__name__)


"""
Issue with function - will run in n^2 comparing each FileSchema with FileSchema, making API call for each

Can reduce LLM API calls by starting with the following process 
-> Check providing system and consuming system
-> Check consuming systems outbound messages
-> Only call LLM on the outbound messages

Alternative solution to bring all attributes and data models into a single file -> run the file on the LLM resulting in 1 very large LLM call
This will reduce token usage but may result in errors

Eligible system check - cut compare area down by looking at system to system connections
e.g. -for every folder in accounts,
        -for every file in credit,
            - get fileSchema
    - for every folder in credit that != accounts (non circular)
        - get all fileSchemas

Chunking plan - block out LLM calls to include all system send messages and all recieving systems in blocks

Caching - save LLM calls to avoid recalling

FOR POC - Call API in O(n^2)
Then optimisation to include separating, chunking & caching not implemented
"""


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


def map_1f_a2a(client: Any, input_file: FileSchema, output_file: FileSchema) -> dict[str, Any]:
    """Map one outbound FileSchema's fields back to one inbound FileSchema's fields.

    Single LLM call per (inbound, outbound) pair. Reuses extraction's
    call/parse machinery (prompt → call → JSON) rather than duplicating it —
    the return shape is deliberately raw dict for now since the FieldLineage
    model isn't agreed yet (see CLAUDE.md open design questions).
    """
    prompt = _build_mapping_prompt(input_file, output_file)
    raw_mapping = extraction.call_llm_extract_schema(client, prompt)

    return {
        "inbound_source": str(input_file.source.path),
        "outbound_source": str(output_file.source.path),
        "mapping": raw_mapping,
    }


def map_f2f(client: Any, files: list[FileSchema]) -> list[dict[str, Any]]:
    # POC: naive N^2 — every file treated as a candidate outbound file mapped
    # against every other file treated as a candidate inbound source.
    # Only map files where the inbound consuming system matches the outbound
    # providing system.
    results: list[dict[str, Any]] = []
    for outbound in files:
        for inbound in files:
            if inbound.source.consuming_system == outbound.source.providing_system:
                results.append(map_1f_a2a(client, inbound, outbound))
    
    
    return results

