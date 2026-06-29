


# cmd K + C
# cmd K + U

# git add .
# git commit -m "title change" -m "description of change"
# git push origin master

import config
import ingestion
import extraction

from pathlib import Path
from typing import Literal, Any
from datamodels import SampleFile, FieldSchema, FileSchema, DomainKnowledge, Ontology, SemanticSchema 


def _testing_message(function_name):
    print("")
    print("-" * 80)
    print(function_name)
    print("-" * 80)
    print("")

# Config

def test_llm_config():
    configuration = config.OllamaLLMClient.load_config()
    for key, value in configuration.items():
        print(f"{key}: {value}")

def test_llm_client():

    prompt = "Why is the sky blue?"
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)

    response = client.chat(prompt)
    print(response)

def test_refactor():
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)
    print(client.chat("Send the numbers 1 to 10 in order"))


# Ingestion

def test_model_directory():
    directory_summary = ingestion.model_directory()
    for sender, receivers in directory_summary.items():
        print(sender)
        for receiver, files in receivers.items():
            print(f" {receiver}")
            for file_path in files:
                print(f" {file_path}")
        print()

def test_parse_directory():
    directory_summary = ingestion.model_directory()
    parsed_directory = ingestion.parse_directory(directory_summary)

    count = 0
    for item in parsed_directory:
        print("Sender: " + item[0] + " -----> Reciever: " + item[1] + " --file_path: " + item[2])
        print("")
        count += 1
    
    print("Counted " + str(count) + " files")

def test_infer_file_format():
    file_type = ingestion.infer_file_format("/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json")
    print("Json file format is: " + file_type)
    file_type = ingestion.infer_file_format("/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.xml")
    print("XML file format is: " + file_type)

def test_load_sample_file():
    sampleFile = ingestion.load_sample_file(["investments", "marketing", "/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json"])
    print(sampleFile.path)
    print(sampleFile.providing_system)
    print(sampleFile.consuming_system)
    print(sampleFile.message_file_name)
    print(sampleFile.file_format)
    print(sampleFile.raw_content)

# Extraction

def test_build_schema_extraction_prompt():
    sampleFile = ingestion.load_sample_file(["investments", "marketing", "/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json"])
    print(extraction.build_schema_extraction_prompt(sampleFile)) 

def test_build_extraction_prompt():
    sampleFile = ingestion.load_sample_file(["investments", "marketing", "/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json"])
    prompt = extraction.build_schema_extraction_prompt(sampleFile)
    print(prompt)

def test_call_llm_extract_schema():
    sampleFile = ingestion.load_sample_file(["investments", "marketing", "/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json"])
    prompt = extraction.build_schema_extraction_prompt(sampleFile)
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)
    response = extraction.call_llm_extract_schema(client, prompt)
    print(response)
    
def test_normalise_schema():
    sampleFile = ingestion.load_sample_file(["investments", "marketing", "/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json"])
    prompt = extraction.build_schema_extraction_prompt(sampleFile)
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)
    response = extraction.call_llm_extract_schema(client, prompt)
    list_of_field_schemas = extraction.normalise_schema(response)
    for item in list_of_field_schemas:
        print(item)
        print(" ")

def test_extract_detailed_schema():
    
    # Set up params to pass in for test
    sampleFile = ingestion.load_sample_file(["investments", "marketing", "/Users/m.wilkinson/Documents/HSBC/data_fabric/App/data/investments/marketing/eligible_customers_for_new_product.json"])
    configuration = config.OllamaLLMClient.load_config()
    client = config.OllamaLLMClient(configuration)

    # Test
    extracted = extraction.extract_detailed_schema(client, sampleFile)
    
    print(extracted.source)
    print(" ")
    for item in extracted.fields:
        print(item)
        print(" ")



if __name__ == "__main__":


    # CONFIG

    _testing_message("TESTING_LLM_CONFIG")
    test_llm_config()
    
    _testing_message("TESTING_LLM_CLIENT")
    test_llm_client()

    _testing_message("TESTING REFACTORED CONFIG")
    test_refactor()

    # INGESTION

    _testing_message("MODEL_DIRECTORY")
    test_model_directory()

    _testing_message("PARSE_DIRECTORY")
    test_parse_directory()

    _testing_message("INFER_FILE_TYPE")
    test_infer_file_format()

    _testing_message("LOADING_SAMPLE_FILE")
    test_load_sample_file()

    # EXTRACTION

    _testing_message("BUILDING_SCHEMA_EXTRACTION_PROMPT")
    test_build_schema_extraction_prompt()

    _testing_message("BUILDING_EXTRACTION_PROMPT")
    test_build_extraction_prompt()
    
    _testing_message("CALLING_LLM_EXTRACT_SCHEMA")
    test_call_llm_extract_schema()

    _testing_message("NORMALISING_SCHEMAS")
    test_normalise_schema()

    _testing_message("TESTING_EXTRACT_DETAILED_SCHEMA")
    test_extract_detailed_schema()

