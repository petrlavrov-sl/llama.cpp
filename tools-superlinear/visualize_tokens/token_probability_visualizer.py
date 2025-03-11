#!/usr/bin/env python3
"""
Token Probability Visualizer

A tool to visualize token probabilities during LLM text generation.
Reads token probability data from stderr output of llama.cpp inference
and visualizes it, coloring tokens based on their absolute or relative probability.

Usage:
  1. Run llama.cpp inference with stderr redirected to a file:
     ./build/bin/llama-run model.gguf "prompt text" 2> inference_log.txt > output.txt
  
  2. Run this script to visualize the token probabilities:
     python token_probability_visualizer.py inference_log.txt output.txt
"""

import re
import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import matplotlib.colors as mcolors
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.patches import Rectangle
import sys
import html
from PIL import Image, ImageDraw, ImageFont
from typing import List, Dict, Tuple, Union, Any, Optional

class TokenProbabilityParser:
    """Parse the stderr log to extract token probability information"""
    
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.rng_blocks = []
        self.tokens = []
        self.probabilities = []
        self.cumulative_probs = []
        self.token_ids = []
        self.token_text = []
        self.selected_indices = []
        
    def parse_log(self) -> List[Dict[str, Any]]:
        """Parse the log file and extract token probability information"""
        with open(self.log_file, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        # Find all RNG blocks
        rng_blocks = re.findall(r'RNG internal:.*?RNG generated sample:.*?token id: (\d+), probability: ([\d\.]+)', 
                               content, re.DOTALL)
        
        probability_blocks = []
        
        rng_block_matches = re.finditer(r'RNG internal:(.*?)RNG generated sample: (\d+) \(token id: (\d+), probability: ([\d\.]+)\)', 
                                        content, re.DOTALL)
        
        for match in rng_block_matches:
            full_text = match.group(0)
            inner_text = match.group(1)
            selected_idx = int(match.group(2))
            token_id = int(match.group(3))
            probability = float(match.group(4))
            
            # Extract token probabilities
            token_probs = re.findall(r'\s+\[(\d+)\] token (\d+) = ([\d\.]+) \(cumulative: ([\d\.]+)\)', inner_text)
            
            # Build token probability data
            token_data = []
            for tp in token_probs:
                idx = int(tp[0])
                token_id_inner = int(tp[1])
                prob = float(tp[2])
                cumulative = float(tp[3])
                
                token_data.append({
                    "index": idx,
                    "token_id": token_id_inner,
                    "probability": prob,
                    "cumulative": cumulative,
                    "selected": idx == selected_idx
                })
            
            # Extract raw random number
            match_raw = re.search(r'- Raw uniform random number: ([\d\.]+)', inner_text)
            raw_random = float(match_raw.group(1)) if match_raw else None
            
            # Extract scaled random number
            match_scaled = re.search(r'- Scaled random number: ([\d\.]+)', inner_text)
            scaled_random = float(match_scaled.group(1)) if match_scaled else None
            
            probability_blocks.append({
                "token_id": token_id,
                "probability": probability,
                "selected_index": selected_idx,
                "raw_random": raw_random,
                "scaled_random": scaled_random,
                "tokens": token_data
            })
            
            # Store for later processing
            self.token_ids.append(token_id)
            self.probabilities.append(probability)
            self.selected_indices.append(selected_idx)
        
        return probability_blocks
    
    def extract_token_text(self, model_vocab_file: Optional[str] = None) -> None:
        """
        Extract text representation of tokens.
        If model_vocab_file is provided, use it to map token IDs to text.
        Otherwise, just use placeholders.
        """
        token_map = {}
        if model_vocab_file and Path(model_vocab_file).exists():
            # Load token map from model vocab file
            # Expected format: one token per line, "token_id token_text"
            with open(model_vocab_file, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    parts = line.strip().split(' ', 1)
                    if len(parts) == 2:
                        token_map[int(parts[0])] = parts[1]
        
        # Map token IDs to text
        for token_id in self.token_ids:
            if token_id in token_map:
                self.token_text.append(token_map[token_id])
            else:
                # Use placeholder if token ID not found in vocab file
                self.token_text.append(f"<{token_id}>")

def load_output_text(output_file: str) -> str:
    """Load the generated text from the output file"""
    try:
        with open(output_file, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading output file: {e}")
        return ""

def create_colored_html(output_text: str, probability_blocks: List[Dict[str, Any]], 
                       color_mode: str = "absolute", output_file: str = "visualization.html"):
    """Create an HTML visualization with tokens colored based on their probabilities"""
    
    # Create HTML template
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Token Probability Visualization</title>
        <style>
            body {{
                font-family: monospace;
                line-height: 1.6;
                margin: 40px;
                background-color: #f5f5f5;
            }}
            
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.1);
            }}
            
            h1 {{
                color: #333;
                text-align: center;
            }}
            
            .token {{
                display: inline-block;
                padding: 2px 4px;
                margin: 2px;
                border-radius: 3px;
                position: relative;
            }}
            
            .token:hover .tooltip {{
                display: block;
            }}
            
            .tooltip {{
                display: none;
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background-color: #333;
                color: white;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 12px;
                white-space: nowrap;
                z-index: 100;
            }}
            
            .legend {{
                margin-top: 20px;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            
            .legend-item {{
                display: flex;
                align-items: center;
                margin-right: 20px;
            }}
            
            .legend-color {{
                width: 20px;
                height: 20px;
                border-radius: 3px;
                margin-right: 5px;
            }}
            
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }}
            
            .mode-selector {{
                margin-left: 20px;
            }}
            
            #text-container {{
                border: 1px solid #ddd;
                padding: 10px;
                border-radius: 3px;
                background-color: #fcfcfc;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Token Probability Visualization</h1>
                <div class="mode-selector">
                    <label>
                        <input type="radio" name="mode" value="absolute" {checked_attr("absolute", color_mode)}>
                        Absolute
                    </label>
                    <label>
                        <input type="radio" name="mode" value="relative" {checked_attr("relative", color_mode)}>
                        Relative
                    </label>
                </div>
            </div>
            
            <div id="text-container">
                {generate_colored_tokens_html(output_text, probability_blocks, color_mode)}
            </div>
            
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background-color: rgb(255,50,50);"></div>
                    <span>High Probability</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: rgb(255,255,50);"></div>
                    <span>Medium Probability</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: rgb(50,255,50);"></div>
                    <span>Low Probability</span>
                </div>
            </div>
        </div>
        
        <script>
            // JavaScript to handle mode switching
            document.querySelectorAll('input[name="mode"]').forEach(input => {{
                input.addEventListener('change', function() {{
                    window.location.href = window.location.pathname + '?mode=' + this.value;
                }});
            }});
        </script>
    </body>
    </html>
    """
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML visualization saved to {output_file}")

def checked_attr(value: str, current_mode: str) -> str:
    """Helper function to set the checked attribute for radio buttons"""
    return "checked" if value == current_mode else ""

def generate_colored_tokens_html(output_text: str, probability_blocks: List[Dict[str, Any]], 
                                color_mode: str) -> str:
    """Generate HTML for colored tokens"""
    
    # Get all probabilities for normalization (relative mode)
    all_probs = [block["probability"] for block in probability_blocks]
    min_prob = min(all_probs) if all_probs else 0
    max_prob = max(all_probs) if all_probs else 1
    prob_range = max_prob - min_prob if max_prob > min_prob else 1.0
    
    # Generate HTML for each token
    html_output = ""
    chars_processed = 0
    
    for i, block in enumerate(probability_blocks):
        token_id = block["token_id"]
        probability = block["probability"]
        
        # Get token text from the output - this is an approximation
        # In practice, you'd need a proper tokenizer to get the exact token text
        # For now, we'll just take the next character as a simple approximation
        if chars_processed < len(output_text):
            token_text = output_text[chars_processed]
            chars_processed += 1
        else:
            token_text = "□"  # Placeholder for tokens outside the output length
        
        # Calculate color based on probability
        if color_mode == "absolute":
            # Absolute mode: green (low) to yellow (medium) to red (high)
            # Map probability [0,1] to color
            r = min(255, int(probability * 2 * 255))
            g = min(255, int((1 - probability) * 2 * 255))
            b = 50
        else:
            # Relative mode: normalize probability within the range of all tokens
            normalized_prob = (probability - min_prob) / prob_range if prob_range > 0 else 0.5
            r = min(255, int(normalized_prob * 2 * 255))
            g = min(255, int((1 - normalized_prob) * 2 * 255))
            b = 50
            
        color = f"rgb({r},{g},{b})"
        
        # Special handling for whitespace characters (make them visible)
        display_text = token_text
        if token_text.isspace():
            if token_text == " ":
                display_text = "&nbsp;"
            elif token_text == "\n":
                display_text = "<br>"
            else:
                display_text = "⎵"  # Unicode symbol for space
        else:
            display_text = html.escape(display_text)
        
        # Create token HTML with tooltip
        token_html = f"""
        <span class="token" style="background-color: {color};">
            {display_text}
            <span class="tooltip">
                Token ID: {token_id}<br>
                Probability: {probability:.4f}
            </span>
        </span>
        """
        
        html_output += token_html
    
    # For any remaining text not processed as tokens
    if chars_processed < len(output_text):
        html_output += html.escape(output_text[chars_processed:])
    
    return html_output

def export_json(probability_blocks: List[Dict[str, Any]], output_file: str):
    """Export probability data to JSON file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(probability_blocks, f, indent=2)
    
    print(f"JSON data exported to {output_file}")

def create_visualization_plot(probability_blocks: List[Dict[str, Any]], output_file: str):
    """Create matplotlib visualization of token probabilities"""
    probabilities = [block["probability"] for block in probability_blocks]
    token_ids = [block["token_id"] for block in probability_blocks]
    
    # Set up plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot probabilities
    ax1.plot(probabilities, marker='o', linestyle='-', color='blue')
    ax1.set_title('Token Probabilities')
    ax1.set_xlabel('Token Sequence')
    ax1.set_ylabel('Probability')
    ax1.grid(True)
    
    # Plot histogram of probabilities
    ax2.hist(probabilities, bins=20, color='green', alpha=0.7)
    ax2.set_title('Probability Distribution')
    ax2.set_xlabel('Probability')
    ax2.set_ylabel('Frequency')
    ax2.grid(True)
    
    # Add statistics
    stats_text = f"""
    Statistics:
    Mean: {np.mean(probabilities):.4f}
    Median: {np.median(probabilities):.4f}
    Min: {min(probabilities):.4f}
    Max: {max(probabilities):.4f}
    Std Dev: {np.std(probabilities):.4f}
    """
    
    fig.text(0.15, 0.02, stats_text, fontsize=10,
             bbox=dict(facecolor='white', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Visualization plot saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Visualize token probabilities from llama.cpp inference")
    parser.add_argument("log_file", help="Log file with stderr output from llama.cpp inference")
    parser.add_argument("output_file", help="Output file with generated text", nargs="?")
    parser.add_argument("--mode", choices=["absolute", "relative"], default="absolute",
                        help="Probability coloring mode: absolute or relative (default: absolute)")
    parser.add_argument("--html", help="Output HTML file (default: visualization.html)", 
                        default="visualization.html")
    parser.add_argument("--json", help="Output JSON file (default: token_probs.json)",
                        default="token_probs.json")
    parser.add_argument("--plot", help="Output plot file (default: token_probs_plot.png)",
                        default="token_probs_plot.png")
    parser.add_argument("--vocab", help="Model vocabulary file for mapping token IDs to text")
    
    args = parser.parse_args()
    
    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Error: Log file '{log_path}' does not exist", file=sys.stderr)
        return 1
    
    # Parse log file
    parser = TokenProbabilityParser(args.log_file)
    probability_blocks = parser.parse_log()
    
    if len(probability_blocks) == 0:
        print("Error: No token probability data found in log file", file=sys.stderr)
        return 1
    
    # Extract token text if vocab file provided
    if args.vocab:
        parser.extract_token_text(args.vocab)
    
    # Export data to JSON
    export_json(probability_blocks, args.json)
    
    # Create visualization plot
    create_visualization_plot(probability_blocks, args.plot)
    
    # If output file is provided, create HTML visualization
    if args.output_file:
        output_path = Path(args.output_file)
        if output_path.exists():
            output_text = load_output_text(args.output_file)
            create_colored_html(output_text, probability_blocks, args.mode, args.html)
        else:
            print(f"Warning: Output file '{output_path}' does not exist. Skipping HTML visualization.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())