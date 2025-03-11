#!/usr/bin/env python3
"""
Utility functions for token visualization.
"""

import json
from typing import List, Dict, Any
from loguru import logger

# def parse_token_data_file(file_path: str, debug: bool = False) -> List[Dict]:
#     """
#     Parse a file containing multiple JSON objects, each spanning multiple lines.
#     Returns a list of parsed JSON objects.
    
#     This is a reusable function that can be imported by other scripts.
#     """
#     # Read the entire file content
#     with open(file_path, 'r') as f:
#         content = f.read()
    
#     # Split the content at each new JSON object start
#     json_objects = []
#     current_obj = ""
#     for line in content.splitlines():
#         line = line.strip()
#         if not line:
#             continue
            
#         if line == "{":  # Start of a new object
#             if current_obj:  # If we have collected a previous object
#                 json_objects.append(current_obj)
#             current_obj = line
#         else:
#             current_obj += line
            
#     # Add the last object if it exists
#     if current_obj:
#         json_objects.append(current_obj)
    
#     # Parse each JSON object
#     parsed_objects = []
#     for json_str in json_objects:
#         try:
#             data = json.loads(json_str)
#             parsed_objects.append(data)
#         except json.JSONDecodeError as e:
#             if debug:
#                 logger.error(f"Failed to parse JSON: {e}")
#                 logger.debug(f"Object start: {json_str[:100]}...")
    
#     return parsed_objects

# def process_token_data(jsonl_file: str, mode: str = 'absolute', debug: bool = False) -> str:
#     """Process token data and return formatted string."""
#     output = []
    
#     # Read the entire file content
#     with open(jsonl_file, 'r') as f:
#         content = f.read()
    
#     # Split the content at each new JSON object start
#     json_objects = []
#     current_obj = ""
#     for line in content.splitlines():
#         line = line.strip()
#         if not line:
#             continue
            
#         if line == "{":  # Start of a new object
#             if current_obj:  # If we have collected a previous object
#                 json_objects.append(current_obj)
#             current_obj = line
#         else:
#             current_obj += line
            
#     # Add the last object if it exists
#     if current_obj:
#         json_objects.append(current_obj)
    
#     # Process each JSON object
#     for json_str in json_objects:
#         try:
#             # Try to parse the JSON
#             data = json.loads(json_str)
            
#             # Extract token info
#             token_id = data.get('selected_token_id')
#             prob = data.get('selected_probability')
            
#             if token_id is None or prob is None:
#                 if debug:
#                     logger.debug(f"Missing token_id or probability in: {json_str[:100]}...")
#                 continue
            
#             # Calculate score
#             if mode == 'relative':
#                 # Get max probability from candidates
#                 candidates = data.get('tokens', [])
#                 if candidates:
#                     max_prob = max(t.get('probability', 0) for t in candidates)
#                     score = 1.0 / (prob / max_prob) if max_prob > 0 else float('inf')
#                 else:
#                     score = 1.0
#             else:  # absolute mode
#                 score = 1.0 / prob if prob > 0 else float('inf')
            
#             # Format output
#             output.append(f"{token_id}({score:.1f})")
            
#         except json.JSONDecodeError as e:
#             if debug:
#                 logger.error(f"Failed to parse JSON: {e}")
#                 logger.debug(f"Object start: {json_str[:100]}...")
#             continue
    
#     if not output:
#         logger.warning("No valid tokens were processed!")
#         return ""
        
#     result = "".join(output)
#     logger.info(f"Processed {len(output)} tokens successfully")
#     return result 




def load_jsonl(jsonl_file: str, debug: bool = False) -> List[Dict]:
    """Process token data and return formatted string."""
    output = []
    
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
    
    result = []
    # Process each JSON object
    for json_str in json_objects:
        try:
            # Try to parse the JSON
            data = json.loads(json_str)
            
            result.append(data)
        except json.JSONDecodeError as e:
            if debug:
                logger.error(f"Failed to parse JSON: {e}")
                logger.debug(f"Object start: {json_str[:100]}...")
            continue
    
    return result