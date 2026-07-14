
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


def run_workflow(root_dir: Path, hierarchy: dict[str, Any]) -> None:
    """
    Creates File Directory of Mermaid Charts
    """

    # config
    client = config.get_llm_client()

    # ingestion
    directory_as_dict = ingestion.model_directory()
    directory_as_list_of_tuples = ingestion.parse_directory(directory_as_dict)
    directory_as_list_of_samplefiles = []
    for item in directory_as_list_of_tuples:
        directory_as_list_of_samplefiles.append(ingestion.load_sample_file(item))

    # extraction
    
    #TODO : Workflow to check if schema exists, if so loads schema, if not extracts and stores schema
    list_of_fileschemas = extraction.extract_all_schemas(client, directory_as_list_of_samplefiles)


    # mapping

    #TODO : Workflow to check is mapping exists, if so loads mapping, if not determines and stores mapping
    mappings = map.map_f2f(client=client, files=list_of_fileschemas)


    raise NotImplementedError