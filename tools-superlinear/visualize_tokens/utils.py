#!/usr/bin/env python3
"""
Utility functions for token visualization.
"""

import json
from typing import List, Dict, Any
from loguru import logger

def load_jsonl(jsonl_file: str, debug: bool = False) -> List[Dict]:
    """
    Load a JSONL file containing token data.
    Returns a list of parsed JSON objects.
    """
    # Read the entire file content
    with open(jsonl_file, 'r') as f:
        content = f.read()
    
    # Split the content at each new JSON object start
    json_objects = []
    current_obj = ""
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
            
        if line == "{":  # Start of a new object
            if current_obj:  # If we have collected a previous object
                json_objects.append(current_obj)
            current_obj = line
        else:
            current_obj += line
            
    # Add the last object if it exists
    if current_obj:
        json_objects.append(current_obj)
    
    # Parse each JSON object
    parsed_objects = []
    for json_str in json_objects:
        try:
            data = json.loads(json_str)
            parsed_objects.append(data)
        except json.JSONDecodeError as e:
            if debug:
                logger.error(f"Failed to parse JSON: {e}")
                logger.debug(f"Object start: {json_str[:100]}...")
    
    return parsed_objects