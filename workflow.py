
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
import graph
import viewer


def run_workflow() -> None:
    """
    Creates File Directory
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
    list_of_fileschemas = extraction.extract_all_schemas(client=client, samples=directory_as_list_of_samplefiles)

    # mapping
    mappings = map.map_f2f(client=client, files=list_of_fileschemas)

    # graph
    ui = graph.graph_all_mappings()

    # viewer — writes viewer.html + viewer_data.js from mappings/ and mermaids/
    viewer.write_viewer()

    return