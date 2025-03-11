#!/usr/bin/env python3
"""
Generate an HTML visualization of tokens with colors based on their probabilities.

Two modes available:
- absolute: shows 1/p where p is the absolute probability
- relative: shows 1/(p/max(candidates)) where p is the token's probability
"""

import argparse
import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from loguru import logger
import html

# Import the token loading function
from utils import load_jsonl

def get_color_for_score(score, max_score=10.0, cmap_name='plasma'):
    """Get a color for a score using a colormap"""
    # Normalize score to 0-1 range
    normalized_score = min(score, max_score) / max_score
    # Get colormap
    cmap = plt.get_cmap(cmap_name)
    # Get color
    color = cmap(normalized_score)
    # Convert to hex
    hex_color = mcolors.rgb2hex(color)
    return hex_color

def create_html_visualization(tokens, output_file, mode='absolute'):
    """Create an HTML visualization of tokens with colors based on their probabilities"""
    if not tokens:
        logger.error("No tokens to visualize")
        return False
    
    # Extract token info
    token_data = []
    
    for token_data_obj in tokens:
        if 'selected_probability' in token_data_obj and 'selected_token_id' in token_data_obj:
            prob = token_data_obj['selected_probability']
            token_id = token_data_obj['selected_token_id']
            
            # Calculate score based on mode
            if mode == 'relative':
                # Get max probability from candidates
                candidates = token_data_obj.get('tokens', [])
                if candidates:
                    max_prob = max(t.get('probability', 0) for t in candidates)
                    score = 1.0 / (prob / max_prob) if max_prob > 0 else float('inf')
                else:
                    score = 1.0
            else:  # absolute mode
                score = 1.0 / prob if prob > 0 else float('inf')
            
            # Get color for score
            color = get_color_for_score(min(score, 10.0))
            
            # Add to token data
            token_data.append({
                'token_id': token_id,
                'probability': prob,
                'score': score,
                'color': color
            })
    
    if not token_data:
        logger.error("No valid token data found")
        return False
    
    # Create HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Token Visualization ({mode} mode)</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }}
        .token {{
            display: inline-block;
            padding: 2px 4px;
            margin: 2px;
            border-radius: 3px;
            cursor: pointer;
        }}
        .tooltip {{
            position: relative;
            display: inline-block;
        }}
        .tooltip .tooltiptext {{
            visibility: hidden;
            width: 200px;
            background-color: #555;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 5px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
        }}
        .tooltip:hover .tooltiptext {{
            visibility: visible;
            opacity: 1;
        }}
        .legend {{
            margin-top: 20px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #f9f9f9;
        }}
        .legend-item {{
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-right: 5px;
            vertical-align: middle;
        }}
        .mode-selector {{
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <h1>Token Visualization</h1>
    
    <div class="mode-selector">
        <strong>Mode:</strong>
        <label>
            <input type="radio" name="mode" value="absolute" {"checked" if mode == 'absolute' else ""}>
            Absolute (1/p)
        </label>
        <label>
            <input type="radio" name="mode" value="relative" {"checked" if mode == 'relative' else ""}>
            Relative (1/(p/max_p))
        </label>
    </div>
    
    <div class="token-container">
"""
    
    # Add tokens
    for i, token in enumerate(token_data):
        token_id = token['token_id']
        prob = token['probability']
        score = token['score']
        color = token['color']
        
        html_content += f"""
        <div class="tooltip">
            <span class="token" style="background-color: {color};">T{token_id}</span>
            <span class="tooltiptext">
                Token ID: {token_id}<br>
                Probability: {prob:.6f}<br>
                Score: {score:.2f}
            </span>
        </div>"""
    
    # Add legend
    html_content += """
    <div class="legend">
        <h3>Legend</h3>
        <p>Colors represent token scores (1/probability):</p>
"""
    
    # Add legend items
    for i in range(11):
        score = i
        color = get_color_for_score(score)
        html_content += f"""
        <div>
            <span class="legend-item" style="background-color: {color};"></span>
            Score: {score}
        </div>"""
    
    # Close HTML
    html_content += """
    </div>
    
    <script>
        // Add mode switching functionality
        document.querySelectorAll('input[name="mode"]').forEach(radio => {
            radio.addEventListener('change', function() {
                if (this.checked) {
                    window.location.href = window.location.pathname + '?mode=' + this.value;
                }
            });
        });
    </script>
</body>
</html>
"""
    
    # Write HTML to file
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    logger.success(f"HTML visualization saved to {output_file}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Token HTML visualizer")
    parser.add_argument("input_file", help="Input file with token data")
    parser.add_argument("--mode", choices=['absolute', 'relative'], default='absolute',
                       help="Probability mode: absolute (1/p) or relative (1/(p/max_p))")
    parser.add_argument("--output", "-o", help="Output file (default: token_visualization.html)",
                       default="token_visualization.html")
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
        
        # Create HTML visualization
        if not create_html_visualization(tokens, args.output, args.mode):
            logger.error("Failed to create HTML visualization")
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