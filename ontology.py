
# ---------------------------------------------------------------------------
# 4 · Business-concept / ontology layer  (ontology.py)
# ---------------------------------------------------------------------------
 
from typing import Literal, Any
from datamodels import SampleFile, FieldSchema, FileSchema, DomainKnowledge, Ontology, SemanticSchema
 
def infer_business_entities(client: Any, kb: DomainKnowledge) -> dict[str, list[str]]:
    """Group canonical fields into business concepts (Customer, Account, Loan…)."""
    raise NotImplementedError
 
 
def infer_entity_relationships(
    client: Any, entities: dict[str, list[str]]
) -> list[tuple[str, str, str]]:
    """Derive (subject, predicate, object) relationships between entities."""
    raise NotImplementedError
 
 
def map_fields_to_concepts(
    kb: DomainKnowledge, entities: dict[str, list[str]]
) -> dict[str, str]:
    """Attach each canonical field to ``Entity.attribute``."""
    raise NotImplementedError
 
 
def build_ontology(client: Any, kb: DomainKnowledge) -> Ontology:
    """Top-level goal-3 orchestrator: entities → relationships → field map."""
    raise NotImplementedError
 
 
def validate_ontology(ontology: Ontology, kb: DomainKnowledge) -> list[str]:
    """Check every source field maps somewhere; return list of orphan fields."""
    raise NotImplementedError
 
 