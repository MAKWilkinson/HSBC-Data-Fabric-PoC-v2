

Project name — Data Fabric - Initial Creation Tool for PoC

Description — Takes input and output send messages between interconnected systems and creates and maps the input data models to the output data models with any transformations possible. Used to help assist with determining  lineage through systems.

Constraints - 
1. LLM calls must be on reasonably sized files that can comfortably fit into a context window. Code not set up to slice and manage large recurring data sets yet.
2. LLM Extraction can fail resulting in non-perfect json format. Currently this will crash system - need to put in place error handling
3. LLM calls for File-to-File mapping are currently done in O(n^2). Do not call on large number of documents, used for PoC only. 
4. AI inferrence used for comparison, will result in some incorrect schema mappings

Installation — Install all requirements.txt dependencies. Set up Ollama on default port. Structure Data folder as below with messages required. Run from app.py.

    data/
    ├── Providing System 1/
    │   ├── Consuming System 1/
    │   │   ├── message_file 1/
    │   │   ├── message_file 2/
    │   │   └── ...
    │   ├── Consuming System 2/
    │   └── ...
    ├── Providing System 2/
    │   └── ...
    └── ...

Usage — Where you have many interfaces and various style send messages and need to model business and schemas in uniform way.

Features — TODO

Tech stack — For PoC... set up using Ollama. To switch LLM create new class that conforms to LLMClient protocol in config.py.

Contributions — 
- Prompt improvements to get closer mappings and more meaningful relatedness scoring
- Stub functions for validations implemented to ensure LLM output is correct, currently no error handling and conformance issues to the data models will crash system.
- Allow parsing of large files to take meaningful sections for input into LLM i.e. first 1000 characters, middle 1000 characters and last 1000 characters to go into prompt. This will result in at most 3000 characters being injected into the promopt and should be able to extract schema regardless of length.
- Perform jaccard index or some other matching system with schemas to do file to file mapping prior to LLM calls. Current model runs n^2 LLM calls which is unsustainable for larger file cross sections. 
- Implement persistence.py multiway parsing of Json to allow LLM output to be stored in JSON but then also extracted from the JSON. This avoids repeated LLM calls in testing. Needs to be done for both Extraction and Mapping.
- Implement storage of raw LLM respones in .txt files for debugging


License — Follow Ollama Licensing rules for all messages stored in data folder.

Contact — m.wilkinson@reply.com