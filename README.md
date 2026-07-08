

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

Tech stack — For PoC... set up using Ollama. To switch LLM create new wrapper class that conforms to LLMClient protocol in config.py.

Contributing — Further improvements requiring contributions include... Prompt improvement, Stub Func completion,

License — Follow Ollama Licensing rules for all messages stored in data folder.

Contact — m.wilkinson@reply.com