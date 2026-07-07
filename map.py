

from typing import Literal, Any
from datamodels import SampleFile, FieldSchema, FileSchema



def build_mapping_prompt():
    pass


# TODO: confirm return types of functions - how will f2f and a2a be mapped?
def mapf2f(client: Any, files: list[FileSchema]) -> Any:
    """


    Issue with function - will run in n^2 comparing each FileSchema with FileSchema, making API call for each

    Can reduce LLM API calls by starting with the following process 
    -> Check providing system and consuming system
    -> Check consuming systems outbound messages
    -> Only call LLM on the outbound messages

    Alternative solution to bring all attributes and data models into a single file -> run the file on the LLM resulting in 1 very large LLM call
    This will reduce token usage but may result in errors
    
    -> option to resolve using combinatorial llm calls e.g. 1 llm call per input to output mapping
    -> 

    Chunking plan 
    
    NON CIRCULAR LOOP

    e.g. -for every folder in accounts,
            -for every file in credit,
                - get fileSchema
        - for every folder in credit that != accounts (non circular)
            - get all fileSchemas
    
            
    FOR POC- CALL IN NSquared???

    Then optimisation to include chunking, caching, 

    """


    pass




def mapa2a(input_file: FileSchema, output_file: FileSchema) -> Any:
    """
    
    """
    
    pass

