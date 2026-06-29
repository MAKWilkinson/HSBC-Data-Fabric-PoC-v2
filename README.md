

Project name — Data Fabric - Initial Creation Tool for PoC

Description — Takes send messages between interconnected systems and creates an initial ontology of the business and a semantic schema. Expect at best 70% acccuracy in initial ontology and semantic schema but depends on complexity and clarity in send messages. If PoC is funded then this will be used to create an initial ontology and semantic layer and the tool deprecated for an [input > suggest ontology > confidence score > review > approve > commit > feedback loop] tool to maintain and develop the ontology and semantic schema and start modelling lineage.

Installation — Install all requirements.txt dependencies. Set up Ollama on default port. Structure Data folder as below with messages required. Run from app.py.

    Data/
    ├── Send System 1/
    │   ├── Receiving System 1/
    │   │   ├── send_message_file 1/
    │   │   ├── send_message_file 2/
    │   │   └── ...
    │   ├── Recieveing System 2/
    │   └── ...
    ├── Send System 2/
    │   └── ...
    └── ...

Usage — Where you have many interfaces and various style send messages and need to model business and schemas in uniform way.

Features — TODO

Tech stack — For PoC... set up using Ollama. To switch LLM create new wrapper class that conforms to LLMClient protocol in config.py.

Contributing — Prompt improvement, working on 

License — Follow Ollama Licensing rules for all messages stored in data folder.

Contact — m.wilkinson@reply.com