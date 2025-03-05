#!/usr/bin/env python3
"""
Visualize RNG distributions from llama.cpp
"""

import argparse
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import sys

def read_rng_file(filename):
    """Read RNG values from a file"""
    values = []
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                continue
            
            try:
                value = float(line)
                values.append(value)
            except ValueError:
                continue
    
    return np.array(values)

def visualize_distribution(values, output_file=None):
    """Visualize the distribution of RNG values"""
    plt.figure(figsize=(10, 8))
    
    # Histogram
    plt.subplot(2, 1, 1)
    plt.hist(values, bins=50, alpha=0.7, color='blue', edgecolor='black')
    plt.title('RNG Distribution')
    plt.xlabel('Value')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    mean = np.mean(values)
    median = np.median(values)
    std_dev = np.std(values)
    min_val = np.min(values)
    max_val = np.max(values)
    
    stats_text = (
        f"Statistics:\n"
        f"Count: {len(values)}\n"
        f"Mean: {mean:.6f}\n"
        f"Median: {median:.6f}\n"
        f"Std Dev: {std_dev:.6f}\n"
        f"Min: {min_val:.6f}\n"
        f"Max: {max_val:.6f}"
    )
    plt.figtext(0.15, 0.45, stats_text, fontsize=10, 
                bbox=dict(facecolor='white', alpha=0.8))
    
    # Cumulative distribution
    plt.subplot(2, 1, 2)
    plt.hist(values, bins=50, alpha=0.7, color='green', 
             edgecolor='black', cumulative=True, density=True)
    plt.title('Cumulative Distribution')
    plt.xlabel('Value')
    plt.ylabel('Cumulative Probability')
    plt.grid(True, alpha=0.3)
    
    # Add ideal line for uniform distribution
    x = np.linspace(0, 1, 100)
    y = x  # Ideal uniform CDF is y=x for range [0,1]
    plt.plot(x, y, 'r--', label='Ideal Uniform')
    plt.legend()
    
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file)
        print(f"Visualization saved to {output_file}")
    else:
        plt.show()

def main():
    parser = argparse.ArgumentParser(description="Visualize RNG distributions from llama.cpp")
    parser.add_argument("input_file", help="Input file with RNG values")
    parser.add_argument("-o", "--output", help="Output PNG file (if not specified, display plot)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist", file=sys.stderr)
        return 1
    
    output_file = args.output
    if not output_file and not args.output:
        output_file = input_path.with_suffix('.png')
    
    try:
        values = read_rng_file(input_path)
        if len(values) == 0:
            print(f"Error: No valid RNG values found in '{input_path}'", file=sys.stderr)
            return 1
        
        visualize_distribution(values, output_file)
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 