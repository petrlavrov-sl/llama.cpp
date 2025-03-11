#!/usr/bin/env python3
"""
Generate a plot of token probability distributions.

Two modes available:
- absolute: shows 1/p where p is the absolute probability
- relative: shows 1/(p/max(candidates)) where p is the token's probability
"""

import argparse
import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger

# Import the token loading function
from utils import load_jsonl

def create_probability_plot(tokens, output_file, mode='absolute'):
    """Create a plot of token probabilities"""
    if not tokens:
        logger.error("No tokens to plot")
        return False
    
    # Extract probabilities
    selected_probs = []
    scores = []
    token_ids = []
    
    for token_data in tokens:
        if 'selected_probability' in token_data and 'selected_token_id' in token_data:
            prob = token_data['selected_probability']
            token_id = token_data['selected_token_id']
            
            # Calculate score based on mode
            if mode == 'relative':
                # Get max probability from candidates
                candidates = token_data.get('tokens', [])
                if candidates:
                    max_prob = max(t.get('probability', 0) for t in candidates)
                    score = 1.0 / (prob / max_prob) if max_prob > 0 else float('inf')
                else:
                    score = 1.0
            else:  # absolute mode
                score = 1.0 / prob if prob > 0 else float('inf')
            
            selected_probs.append(prob)
            scores.append(min(score, 10.0))  # Cap at 10 for better visualization
            token_ids.append(token_id)
    
    if not selected_probs:
        logger.error("No valid probabilities found")
        return False
    
    # Create the plot
    plt.figure(figsize=(12, 6))
    
    # Plot 1: Token probabilities
    plt.subplot(1, 2, 1)
    plt.plot(selected_probs, marker='o', linestyle='-', alpha=0.7)
    plt.title(f'Token Probabilities ({mode} mode)')
    plt.xlabel('Token Position')
    plt.ylabel('Probability')
    plt.grid(True, alpha=0.3)
    
    # Plot 2: Token scores (1/probability)
    plt.subplot(1, 2, 2)
    plt.plot(scores, marker='o', linestyle='-', alpha=0.7, color='orange')
    plt.title(f'Token Scores (1/probability) ({mode} mode)')
    plt.xlabel('Token Position')
    plt.ylabel('Score (1/probability)')
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file)
    logger.success(f"Plot saved to {output_file}")
    
    # Also save the data as CSV for further analysis
    csv_file = output_file.replace('.png', '.csv')
    with open(csv_file, 'w') as f:
        f.write("position,token_id,probability,score\n")
        for i, (token_id, prob, score) in enumerate(zip(token_ids, selected_probs, scores)):
            f.write(f"{i},{token_id},{prob},{score}\n")
    logger.success(f"Data saved to {csv_file}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Token probability plot generator")
    parser.add_argument("input_file", help="Input file with token data")
    parser.add_argument("--mode", choices=['absolute', 'relative'], default='absolute',
                       help="Probability mode: absolute (1/p) or relative (1/(p/max_p))")
    parser.add_argument("--output", "-o", help="Output file (default: token_probabilities.png)",
                       default="token_probabilities.png")
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
            
        # Load token data
        tokens = load_jsonl(args.input_file, args.debug)
        
        if not tokens:
            logger.error("No token data loaded")
            return 1
        
        # Create plot
        if not create_probability_plot(tokens, args.output, args.mode):
            logger.error("Failed to create plot")
            return 1
        
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