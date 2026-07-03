
# ---------------------------------------------------------------------------
# 3 · Schema combination → shared domain knowledge  (domain.py)
# ---------------------------------------------------------------------------


from pathlib import Path
from typing import Literal, Any
from datamodels import SampleFile, FieldSchema, FileSchema, DomainKnowledge, Ontology, SemanticSchema 


"""

cluster → alias → relate  → merge

""" 


def cluster_fields_by_similarity(
    schemas: list[FileSchema],
) -> list[list[FieldSchema]]:
    """Group fields that likely share meaning across files (e.g. cust_id/cust_ref)."""

    # CONSIDERING JACCARD vs TF-IDF PATTERN MATCHING
    # Pattern match on description as well as field name? 

    raise NotImplementedError

def resolve_field_aliases(
    client: Any, clusters: list[list[FieldSchema]]
) -> dict[str, list[str]]:
    """LLM-assisted merge of synonymous fields into ``canonical -> aliases``."""
    raise NotImplementedError

def detect_cross_file_relationships(
    schemas: list[FileSchema],
) -> list[tuple[str, str]]:
    """Find shared keys/join points across files (e.g. account_id links)."""
    raise NotImplementedError

def merge_schemas(
    schemas: list[FileSchema],
    aliases: dict[str, list[str]],
    relationships: list[tuple[str, str]],
) -> DomainKnowledge:
    """Produce a unified field catalogue with provenance and relationships."""
    raise NotImplementedError

def build_domain_knowledge_base(schemas: list[FileSchema], client: Any) -> DomainKnowledge:
    """Top-level goal-2 orchestrator: cluster → alias → relate → merge."""
    raise NotImplementedError

