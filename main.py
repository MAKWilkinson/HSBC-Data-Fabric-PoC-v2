

import os
import json
from pathlib import Path
from collections import defaultdict
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple
import hashlib
import base64
from _logging_config import setup_logging

from datamodels import SampleFile, FieldSchema, FileSchema, FieldMapping, FileMapping
from workflow import run_workflow

"""
workflow 
0 - config.py
1 - ingestion.py
2 - extraction.py
3 - map.py

"""

if __name__ == "__main__":
    setup_logging()
    run_workflow()

