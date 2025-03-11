#!/usr/bin/env python3
"""
Simple token visualization script that outputs tokens and their probabilities
in a basic text format: Token1(score1)Token2(score2)...

Two modes available:
- absolute: shows 1/p where p is the absolute probability
- relative: shows 1/(p/max(candidates)) where p is the token's probability
"""

import json
import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

def parse_token_data_file(file_path: str, debug: bool = False) -> List[Dict]:
    """
    Parse a file containing multiple JSON objects, each spanning multiple lines.
    Returns a list of parsed JSON objects.
    
    This is a reusable function that can be imported by other scripts.
    """
    # Read the entire file content
    with open(file_path, 'r') as f:
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
                try:
                    # Try to parse it to validate
                    json_obj = json.loads(current_obj)
                    json_objects.append(json_obj)
                except json.JSONDecodeError as e:
                    if debug:
                        logger.error(f"Failed to parse JSON: {e}")
                        logger.debug(f"Object: {current_obj[:100]}...")
            current_obj = line
        else:
            current_obj += line
            
    # Add the last object if it exists
    if current_obj:
        try:
            json_obj = json.loads(current_obj)
            json_objects.append(json_obj)
        except json.JSONDecodeError as e:
            if debug:
                logger.error(f"Failed to parse last JSON object: {e}")
    
    return json_objects

def process_token_data(jsonl_file: str, mode: str = 'absolute', debug: bool = False) -> str:
    """Process token data and return formatted string."""
    output = []
    
    # Parse the token data file
    json_objects = parse_token_data_file(jsonl_file, debug)
    
    if debug:
        logger.debug(f"Parsed {len(json_objects)} token objects")
    
    # Process each JSON object
    for data in json_objects:
        try:
            # Extract token info
            token_id = data.get('selected_token_id')
            prob = data.get('selected_probability')
            
            if token_id is None or prob is None:
                if debug:
                    logger.debug(f"Missing token_id or probability in object")
                continue
            
            # Calculate score
            if mode == 'relative':
                # Get max probability from candidates
                candidates = data.get('tokens', [])
                if candidates:
                    max_prob = max(t.get('probability', 0) for t in candidates)
                    score = 1.0 / (prob / max_prob) if max_prob > 0 else float('inf')
                else:
                    score = 1.0
            else:  # absolute mode
                score = 1.0 / prob if prob > 0 else float('inf')
            
            # Format output - use token ID directly
            # We'll display it in a more readable format
            if token_id < 256:
                # ASCII characters - show them directly if printable
                try:
                    char = chr(token_id)
                    if char.isprintable():
                        token_display = char
                    else:
                        token_display = f"\\{token_id:03d}"
                except:
                    token_display = f"\\{token_id:03d}"
            else:
                # Non-ASCII token IDs
                token_display = f"T{token_id}"
            
            output.append(f"{token_display}({score:.1f})")
            
        except Exception as e:
            if debug:
                logger.error(f"Error processing token: {e}")
            continue
    
    if not output:
        logger.warning("No valid tokens were processed!")
        return ""
        
    result = "".join(output)
    logger.info(f"Processed {len(output)} tokens successfully")
    return result

def main():
    parser = argparse.ArgumentParser(description="Simple token probability visualizer")
    parser.add_argument("input_file", help="Input file with token data")
    parser.add_argument("--mode", choices=['absolute', 'relative'], default='absolute',
                       help="Probability mode: absolute (1/p) or relative (1/(p/max_p))")
    parser.add_argument("--output", "-o", help="Output file (default: pseudo-colored-output.txt)",
                       default="pseudo-colored-output.txt")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    logger.remove()
    log_level = "DEBUG" if args.debug else "INFO"
    logger.add(sys.stderr, level=log_level, 
              format="<level>{level: <8}</level> | <green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    
    try:
        # Check if input file exists
        if not os.path.exists(args.input_file):
            logger.error(f"Input file not found: {args.input_file}")
            return 1
            
        # Process tokens
        result = process_token_data(args.input_file, args.mode, args.debug)
        
        if not result:
            logger.error("No output generated!")
            return 1
        
        # Write output
        with open(args.output, 'w') as f:
            f.write(result)
            
        logger.success(f"Output written to {args.output}")
        preview = result[:100] + "..." if len(result) > 100 else result
        logger.info(f"Preview: {preview}")
        
    except Exception as e:
        logger.error(f"Failed to process file: {e}")
        if args.debug:
            import traceback
            logger.debug(traceback.format_exc())
        return 1
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main()) 