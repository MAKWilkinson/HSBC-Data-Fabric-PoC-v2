
# ---------------------------------------------------------------------------
# Top-level orchestrator  (pipeline.py)
# ---------------------------------------------------------------------------
 
import config
import ingestion
import extraction


from pathlib import Path
from typing import Literal, Any
from datamodels import SampleFile, FieldSchema, FileSchema, DomainKnowledge, Ontology, SemanticSchema 

def run_pipeline(root_dir: Path, hierarchy: dict[str, Any]) -> SemanticSchema:
    """Chain goals 1→5: ingest → extract → domain KB → ontology → semantic schema."""

    # configs
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)

    # ingestion
    directory_as_dict = ingestion.model_directory()
    directory_as_list_of_tuples = ingestion.parse_directory(directory_as_dict)
    directory_as_list_of_sampleFiles = []
    for item in directory_as_list_of_tuples:
        directory_as_list_of_sampleFiles.append(ingestion.load_sample_file(item))

    # extraction
    list_of_FileSchemas = extraction.extract_all_schemas(client, directory_as_list_of_sampleFiles)

    # domain knowledge base


    # ontology


    # semantic schema


    raise NotImplementedError