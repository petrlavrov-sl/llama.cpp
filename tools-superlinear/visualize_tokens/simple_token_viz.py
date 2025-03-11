#!/usr/bin/env python3
"""
Simple token visualization script that outputs tokens and their probabilities
in a basic text format: Token1(score1)Token2(score2)...

Two modes available:
- absolute: shows 1/p where p is the absolute probability
- relative: shows 1/(p/max(candidates)) where p is the token's probability
"""

import argparse
import os

from loguru import logger

# Import the token loading function
from utils import load_jsonl


def process_token_data(jsonl_file: str, mode: str = 'absolute', debug: bool = False) -> str:
    """Process token data and return formatted string."""
    output = []
    
    # Load the token data
    json_objects = load_jsonl(jsonl_file, debug)
    
    if debug:
        logger.debug(f"Loaded {len(json_objects)} token objects")
    
    # Process each token object
    for data in json_objects:
        try:
            # Extract token info
            token_id = data.get('selected_token_id')
            prob = data.get('selected_probability')
            
            if token_id is None or prob is None:
                if debug:
                    logger.debug(f"Missing token_id or probability in object")
                continue
            
            # Calculate score based on mode
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
            
            # Format output with token ID
            output.append(f"{token_id}({score:.1f})")
            
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