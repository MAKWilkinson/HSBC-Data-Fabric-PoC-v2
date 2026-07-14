
# ---------------------------------------------------------------------------
# Top-level orchestrator  (workflow.py)
# ---------------------------------------------------------------------------
 
from pathlib import Path
from typing import Literal, Any

from datamodels import SampleFile, FieldSchema, FileSchema, FieldMapping, FileMapping
import config
import ingestion
import extraction
import map

# TODO: Update return type when defined new data models
def run_workflow(root_dir: Path, hierarchy: dict[str, Any]) -> Any:
    """
    
    TODO: update workflow to include caching of prompts / file schemas to avoid repeated calls on LLM for same work

    """

    # configs
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)

    # ingestion
    directory_as_dict = ingestion.model_directory()
    directory_as_list_of_tuples = ingestion.parse_directory(directory_as_dict)
    directory_as_list_of_samplefiles = []
    for item in directory_as_list_of_tuples:
        directory_as_list_of_samplefiles.append(ingestion.load_sample_file(item))

    # extraction
    list_of_fileschemas = extraction.extract_all_schemas(client, directory_as_list_of_samplefiles)


    # mapping
    mappings = map.map_f2f(client=client, files=list_of_fileschemas)


    raise NotImplementedError