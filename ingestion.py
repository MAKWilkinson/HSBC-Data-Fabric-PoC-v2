
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
2. within data dir is a list of dirs representing systems sending data
3. within each sending system dir is a list of dirs representing systems recieving data
4. within each recieving system dir is a list of sample files
5. this is extracted into SampleFile data model representing the file and file contents as str

Future considerations:
1. Including tertiary dir's representing system messages and including multiple sample messages
    improvement would avoid potential non-representative docs being sampled 
    new folder struct [[ data  → sender → reciever → message_type → sample_files ]]
    e.g. data/accounts/customer_services/complaint_api/complaint09-09-09-12-10-01-00-00022312
2. Analyse documents in place rather than extracting to string saving loading into memory
    this will limit use of tokens through base64 encoding doc and using API

"""

def model_directory():
    """
    Find all files in the directory and group them by sender then receiver.
    
    Returns:
        dict: {
            sender (str): {
                receiver (str): [link_to_file (str), ...]
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
    for sender_dir in data_path.iterdir():
        if not sender_dir.is_dir():
            continue

        sender = sender_dir.name
        directory.setdefault(sender, {})

        for receiver_dir in sender_dir.iterdir():
            if not receiver_dir.is_dir():
                continue
            
            receiver = receiver_dir.name
            directory[sender].setdefault(receiver, [])

            for item in receiver_dir.iterdir():
                if item.is_file():
                    directory[sender][receiver].append(str(item.resolve()))
                else:
                    continue

    return directory
 
def parse_directory(directory: dict[dict, list]) -> list[tuple[str, str, str]]:
    """
    Flatten the sender → reciever → file_path structure into 
    (sender, reciever, file_path) tuples.

    Returns:
        List (sender (str), reciever (str), link_to_file (str))

    """
    result = []
    for sender, receivers in directory.items():
        for receiver, file_paths in receivers.items():
            for file_path in file_paths:
                result.append((sender, receiver, file_path))
    return result
 
def infer_file_format(path: str) -> Literal["json", "csv", "xml", "avro",]:
    """Detect a file's serialization format from extension/content."""
    return Path(path).suffix.lstrip(".")
 
def load_sample_file(parsed_file) -> SampleFile:
    """
    Read one file and wrap its content + context in a ``SampleFile``.
    
    parsed file is tuple[sender, reciever, filepath,]
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
        parent_system=parsed_file[0], # system sending file
        child_system=parsed_file[1], # system recieving file
        message_file_name=name,  # e.g. "loan_application_data"
        file_format=inferred_file_format,
        raw_content=content,
    )


