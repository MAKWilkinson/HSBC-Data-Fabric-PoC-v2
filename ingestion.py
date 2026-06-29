
# ---------------------------------------------------------------------------
# 1 · Discovery & ingestion  (ingestion.py)
# ---------------------------------------------------------------------------

import os
from pathlib import Path
from typing import Literal
from datamodels import SampleFile, FieldSchema, FileSchema, DomainKnowledge, Ontology, SemanticSchema


"""

ASSUMPTION: Systems are uniquely named and typed correctly and consistently

Ingestion process currently is:
1. look in "data" dir
2. within data dir is a list of dirs representing systems providing data
3. within each providing system dir is a list of dirs representing systems consuming data
4. within each consuming system dir is a list of sample files
5. this is extracted into SampleFile data model representing the file and file contents as str

Future considerations:
1. Including tertiary dir's representing system messages and including multiple sample messages
    improvement would avoid potential non-representative docs being sampled 
    new folder struct [[ data  → provider → consumer → message_type → sample_files ]]
    e.g. data/accounts/customer_services/complaint_api/complaint09-09-09-12-10-01-00-00022312
2. Analyse documents in place rather than extracting to string saving loading into memory
    this will limit use of tokens through base64 encoding doc and using API

"""

def model_directory():
    """
    Find all files in the directory and group them by provider then consumer.
    
    Returns:
        dict: {
            provider (str): {
                consumer (str): [link_to_file (str), ...]
            }
        }
    """
    
    # Get the directory containing this Python file
    script_path = Path(__file__).resolve()
    script_dir = script_path.parent
    
    # Construct path to data folder where data is stored
    data_path = script_dir / "data"
    
    # Check if data directory exists
    if not data_path.is_dir():
        print(f"Warning: {data_path} does not exist")
        return {}
    
    # Create dictionary to store file paths in
    directory = {}

    # Traverse file paths and add to dictionary
    for provider_dir in data_path.iterdir():
        if not provider_dir.is_dir():
            continue

        sender = provider_dir.name
        directory.setdefault(sender, {})

        for consumer_dir in provider_dir.iterdir():
            if not consumer_dir.is_dir():
                continue
            
            consumer = consumer_dir.name
            directory[sender].setdefault(consumer, [])

            for item in consumer_dir.iterdir():
                if item.is_file():
                    directory[sender][consumer].append(str(item.resolve()))
                else:
                    continue

    return directory
 
def parse_directory(directory: dict[dict, list]) -> list[tuple[str, str, str]]:
    """
    Flatten the provider → consumer → file_path structure into 
    (provider, consumer, file_path) tuples.

    Returns:
        List (provider (str), consumer (str), link_to_file (str))

    """
    result = []
    for provider, consumers in directory.items():
        for consumer, file_paths in consumers.items():
            for file_path in file_paths:
                result.append((provider, consumer, file_path))
    return result
 
def infer_file_format(path: str) -> Literal["json", "csv", "xml", "avro",]:
    """Detect a file's serialization format from extension/content."""
    return Path(path).suffix.lstrip(".")
 
def load_sample_file(parsed_file) -> SampleFile:
    """
    Read one file and wrap its content + context in a ``SampleFile``.
    
    parsed file is tuple[provider, consumer, filepath,]
    """

    file_path = Path(parsed_file[2])
    

    # Read file name
    name = file_path.name

    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    
    # Infer format from file extension
    inferred_file_format = infer_file_format(parsed_file[2])
    
    # Create and return SampleFile model
    return SampleFile(
        path=file_path,
        providing_system=parsed_file[0], # system providing file
        consuming_system=parsed_file[1], # system consuming file
        message_file_name=name,  # e.g. "loan_application_data"
        file_format=inferred_file_format,
        raw_content=content,
    )


